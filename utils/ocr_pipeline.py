"""
Lightweight OCR pipeline using ONNX Runtime (no PyTorch dependency).
Combines YOLO detection and OCR without saving intermediate crops.
"""
import argparse
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort
import re
import csv
import shutil
import sys
from paddleocr import PaddleOCR

try:
    import onnx
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

def setup_args():
    parser = argparse.ArgumentParser(description="Detect and OCR product names and prices")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to image or directory")
    parser.add_argument("--model", "-m", type=str, required=True, help="Path to YOLO ONNX model")
    parser.add_argument("--output", "-o", type=str, default="ocr_results.csv", help="Output CSV file")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--img-size", type=int, default=640, help="Input image size")
    parser.add_argument("--lang", type=str, default="de", help="OCR language")
    return parser.parse_args()

def ensure_model_compatibility(onnx_path: str):
    """
    Ensures the ONNX model exists and has a compatible IR version (<= 8 for broad compatibility).
    If ONNX is missing but .pt exists, exports it.
    If IR version is too high, patches it.
    """
    onnx_path = Path(onnx_path)
    pt_path = onnx_path.with_suffix('.pt')
    
    # 1. Export if missing
    if not onnx_path.exists():
        if pt_path.exists():
            print(f"[INFO] ONNX model not found, exporting from {pt_path}...")
            try:
                from ultralytics import YOLO
                model = YOLO(str(pt_path))
                # Export with opset 11 to attempt compatibility
                model.export(format="onnx", opset=11)
                print(f"[INFO] Export complete: {onnx_path}")
            except ImportError:
                print(f"[ERROR] 'ultralytics' not installed. Cannot export from .pt. Please install it or provide .onnx file.")
                sys.exit(1)
            except Exception as e:
                print(f"[ERROR] Export failed: {e}")
                sys.exit(1)
        else:
            print(f"[ERROR] Model not found: {onnx_path} (and no source .pt found)")
            sys.exit(1)

    # 2. Check and Patch IR Version
    if HAS_ONNX:
        try:
            model = onnx.load(str(onnx_path))
            current_ir = model.ir_version
            # IR 8 corresponds to ONNX 1.7, widely supported.
            # Some runtimes (like older ORT or specific builds) fail with IR > 11.
            TARGET_IR = 8 
            
            if current_ir > 11: # Threshold where we saw errors
                print(f"[WARN] Model IR version is {current_ir} (high). Patching to IR {TARGET_IR} for compatibility...")
                
                # Backup
                backup_path = onnx_path.with_suffix('.onnx.bak')
                if not backup_path.exists():
                    shutil.copy2(onnx_path, backup_path)
                
                model.ir_version = TARGET_IR
                onnx.save(model, str(onnx_path))
                print(f"[INFO] Patched model saved to {onnx_path}")
            else:
                print(f"[INFO] Model IR version {current_ir} is compatible.")
        except Exception as e:
            print(f"[WARN] Failed to check/patch ONNX model: {e}")
    else:
        print("[WARN] 'onnx' module not found. Skipping IR version check/patching.")

def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    """Resize and pad image while maintaining aspect ratio."""
    shape = img.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img, r, (dw, dh)

def preprocess(img, img_size=640):
    """Preprocess image for YOLO inference."""
    img_resized, ratio, (dw, dh) = letterbox(img, new_shape=img_size)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    img_normalized = img_rgb.astype(np.float32) / 255.0
    img_transposed = np.transpose(img_normalized, (2, 0, 1))
    img_batched = np.expand_dims(img_transposed, axis=0)
    return img_batched, ratio, (dw, dh)

def xywh2xyxy(x):
    """Convert nx4 boxes from [x, y, w, h] to [x1, y1, x2, y2]."""
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y

def nms(boxes, scores, iou_threshold=0.45):
    """Non-maximum suppression."""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]
    
    return keep

def postprocess(output, img_shape, input_shape, conf_threshold=0.25, iou_threshold=0.45):
    """Post-process YOLO output."""
    # ONNX output is (1, 6, 8400) - need to transpose to (1, 8400, 6)
    predictions = np.transpose(output, (0, 2, 1))[0]  # Now (8400, 6)
    
    # predictions format: [x, y, w, h, conf_class0, conf_class1]
    # For YOLOv8/v11, there's no separate objectness score
    # The class confidences are already the final scores
    
    # Get max class confidence and class ID for each detection
    class_scores = predictions[:, 4:]  # (8400, 2) - confidences for Name and Price
    class_ids = np.argmax(class_scores, axis=1)  # (8400,)
    confidences = np.max(class_scores, axis=1)  # (8400,)
    
    # Filter by confidence threshold
    mask = confidences > conf_threshold
    predictions = predictions[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]
    
    if len(predictions) == 0:
        return np.array([]), np.array([]), np.array([])
    
    # Convert boxes from xywh to xyxy
    boxes = xywh2xyxy(predictions[:, :4])
    
    # Scale boxes to original image size
    img_h, img_w = img_shape
    input_h, input_w = input_shape
    scale = min(input_w / img_w, input_h / img_h)
    pad_w = (input_w - img_w * scale) / 2
    pad_h = (input_h - img_h * scale) / 2
    
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_w) / scale
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_h) / scale
    boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, img_w)
    boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, img_h)
    
    # Apply NMS
    keep_indices = nms(boxes, confidences, iou_threshold)
    return boxes[keep_indices], confidences[keep_indices], class_ids[keep_indices]

def clean_price(text):
    """Extract and format price from OCR text."""
    text = text.replace("€", "").strip()
    match = re.search(r'(\d+)[.,](\d{2})', text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return text

def main():
    args = setup_args()
    
    input_path = Path(args.input)
    
    # Ensure model compatibility (Export/Patch)
    ensure_model_compatibility(args.model)
    
    # Load ONNX model
    print(f"Loading YOLO ONNX model: {args.model}")
    try:
        session = ort.InferenceSession(args.model, providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        print("[TIP] If this is a version error, ensure 'onnx' is installed so the script can auto-patch the model.")
        sys.exit(1)

    input_name = session.get_inputs()[0].name
    
    # Initialize PaddleOCR (use CPU to avoid CUDA conflicts)
    print("Initializing PaddleOCR...")
    # use_gpu is often inferred or passed differently in newer versions. 
    # use_angle_cls might be deprecated for use_textline_orientation but we'll stick to defaults or minimal args.
    ocr = PaddleOCR(use_angle_cls=True, lang=args.lang) 
    print("PaddleOCR initialized.")
    
    # Get files
    if input_path.is_dir():
        files = sorted([p for p in input_path.glob("*") if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']])
    else:
        files = [input_path]
        
    print(f"\nProcessing {len(files)} images...")
    
    results = []
    
    for i, file_path in enumerate(files):
        print(f"\n[{i+1}/{len(files)}] Processing {file_path.name}...")
        
        # Read image
        img = cv2.imread(str(file_path))
        if img is None:
            print(f"  Warning: Could not read {file_path}")
            continue
        
        img_h, img_w = img.shape[:2]
        
        # Preprocess for YOLO
        input_tensor, ratio, (dw, dh) = preprocess(img, args.img_size)
        
        # Run YOLO inference
        outputs = session.run(None, {input_name: input_tensor})
        
        # Postprocess YOLO output
        boxes, confidences, class_ids = postprocess(
            outputs[0], 
            (img_h, img_w), 
            (args.img_size, args.img_size),
            args.conf
        )
        
        # Process detections
        names = []
        prices = []
        
        for box, conf, cls_id in zip(boxes, confidences, class_ids):
            x1, y1, x2, y2 = map(int, box)
            
            # Crop region in memory
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            
            # Run OCR on crop
            ocr_result = ocr.ocr(crop)
            
            # Extract text
            text = ""
            if ocr_result and ocr_result[0]:
                text = " ".join([line[1][0] for line in ocr_result[0]])
            
            # Store detection with OCR result
            detection = {
                'class_id': int(cls_id),
                'conf': float(conf),
                'box': [x1, y1, x2, y2],
                'text': text
            }
            
            if cls_id == 0:  # Name
                names.append(detection)
            elif cls_id == 1:  # Price
                prices.append(detection)
        
        # Combine results
        names.sort(key=lambda x: x['box'][1])
        full_name = " ".join([n['text'] for n in names])
        
        best_price = ""
        if prices:
            prices.sort(key=lambda x: (x['box'][3] - x['box'][1]), reverse=True)
            raw_price = prices[0]['text']
            best_price = clean_price(raw_price)
        
        print(f"  -> Name: {full_name}")
        print(f"  -> Price: {best_price}")
        
        results.append({
            "filename": file_path.stem,
            "name": full_name,
            "price": best_price
        })
    
    # Save to CSV
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'name', 'price'])
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✓ Results saved to {args.output}")
    print(f"✓ Processed {len(results)} images")

if __name__ == "__main__":
    main()

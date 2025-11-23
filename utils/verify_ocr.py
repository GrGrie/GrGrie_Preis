import os
import argparse
import cv2
import re
import csv
from paddleocr import PaddleOCR
from pathlib import Path
import numpy as np
from ultralytics import YOLO

def setup_args():
    parser = argparse.ArgumentParser(description="Verify OCR extraction")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to image or directory")
    parser.add_argument("--output", "-o", type=str, default="eval-results/ocr_verification", help="Output directory")
    parser.add_argument("--lang", type=str, default="de", help="OCR language")
    parser.add_argument("--layout_model", type=str, help="Path to YOLO layout detection model (.pt or .onnx)")
    return parser.parse_args()

def get_box_height(box):
    # box is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    ys = [p[1] for p in box]
    return max(ys) - min(ys)

def get_box_center_y(box):
    ys = [p[1] for p in box]
    return sum(ys) / 4

def clean_price(text):
    # Remove currency symbols and non-numeric chars except , .
    # Common OCR errors: '1.39' -> '1.39', '1,39' -> '1,39', '1 39' -> '1.39'
    text = text.replace("€", "").strip()
    # Check for price pattern
    match = re.search(r'(\d+)[.,](\d{2})', text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return None

def extract_info_heuristic(ocr_result, img_height):
    if not ocr_result:
        return None, None, None, None

    lines = []
    # Check for new format (list of dicts)
    if isinstance(ocr_result, list) and len(ocr_result) > 0 and isinstance(ocr_result[0], dict):
        res = ocr_result[0]
        if 'rec_texts' in res and 'rec_polys' in res:
            texts = res['rec_texts']
            boxes = res['rec_polys']
            scores = res.get('rec_scores', [1.0]*len(texts))
            for box, text, score in zip(boxes, texts, scores):
                lines.append([box, (text, score)])
    # Check for old format (list of lists)
    elif isinstance(ocr_result, list) and len(ocr_result) > 0 and isinstance(ocr_result[0], list):
         lines = ocr_result[0]
    
    if not lines:
        return None, None, None, None

    # 1. Identify Price
    potential_prices = []
    other_texts = []

    for line in lines:
        box = line[0]
        text, conf = line[1]
        height = get_box_height(box)
        
        price_val = clean_price(text)
        if price_val:
            potential_prices.append({'text': text, 'value': price_val, 'height': height, 'box': box, 'conf': conf})
        else:
            other_texts.append({'text': text, 'height': height, 'box': box, 'conf': conf})

    best_price = None
    if potential_prices:
        best_price = max(potential_prices, key=lambda x: x['height'])

    # 2. Identify Name
    if not other_texts:
        return best_price['value'] if best_price else None, None, best_price, []

    max_height = max([t['height'] for t in other_texts]) if other_texts else 0
    
    name_candidates = []
    for t in other_texts:
        text = t['text'].strip()
        if t['height'] < max_height * 0.4: continue
        if '%' in text or re.match(r'^-\d+', text): continue
        if text.isdigit() and len(text) < 3: continue
        name_candidates.append(t)
    
    name_candidates.sort(key=lambda x: get_box_center_y(x['box']))
    
    extracted_name = " ".join([t['text'] for t in name_candidates])
    extracted_price = best_price['value'] if best_price else ""

    return extracted_name, extracted_price, best_price, name_candidates

def process_with_yolo(ocr, layout_model_path, file_path, debug_dir):
    model = YOLO(layout_model_path)
    results = model(str(file_path))
    
    img = cv2.imread(str(file_path))
    extracted_name = ""
    extracted_price = ""
    
    debug_img = img.copy()
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            cls = int(box.cls[0]) # 0=Name, 1=Price
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # Crop (in-memory)
            crop = img[y1:y2, x1:x2]
            if crop.size == 0: continue
            
            # OCR on crop
            ocr_res = ocr.ocr(crop)
            
            # Extract text
            text = ""
            if isinstance(ocr_res, list) and len(ocr_res) > 0:
                 # Handle both formats
                if isinstance(ocr_res[0], dict) and 'rec_texts' in ocr_res[0]:
                    text = " ".join(ocr_res[0]['rec_texts'])
                elif isinstance(ocr_res[0], list):
                    text = " ".join([line[1][0] for line in ocr_res[0]])
            
            if cls == 0: # Name
                extracted_name = text
                color = (0, 255, 0)
                label = "Name"
            elif cls == 1: # Price
                extracted_price = clean_price(text) or text
                color = (0, 0, 255)
                label = "Price"
            
            # Draw debug
            cv2.rectangle(debug_img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(debug_img, f"{label}: {text}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
    cv2.imwrite(str(debug_dir / f"debug_yolo_{Path(file_path).name}"), debug_img)
    return extracted_name, extracted_price

def draw_debug(img_path, out_path, best_price, name_candidates):
    img = cv2.imread(img_path)
    if img is None: return
    if best_price:
        box = np.array(best_price['box']).astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(img, [box], True, (0, 0, 255), 2)
        cv2.putText(img, f"Price: {best_price['value']}", (int(box[0][0][0]), int(box[0][0][1]-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    if name_candidates:
        for cand in name_candidates:
            box = np.array(cand['box']).astype(np.int32).reshape((-1, 1, 2))
            cv2.polylines(img, [box], True, (0, 255, 0), 2)
            cv2.putText(img, "Name", (int(box[0][0][0]), int(box[0][0][1]-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv2.imwrite(out_path, img)

def main():
    args = setup_args()
    ocr = PaddleOCR(use_angle_cls=True, lang=args.lang)
    
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = output_dir / "debug_images"
    debug_dir.mkdir(exist_ok=True)
    
    files = sorted([p for p in input_path.glob("*") if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']]) if input_path.is_dir() else [input_path]
    
    results = []
    print(f"Processing {len(files)} images...")
    
    for i, file_path in enumerate(files):
        print(f"[{i+1}/{len(files)}] Processing {file_path.name}...")
        try:
            if args.layout_model:
                name, price = process_with_yolo(ocr, args.layout_model, file_path, debug_dir)
            else:
                result = ocr.ocr(str(file_path))
                img = cv2.imread(str(file_path))
                h, w = img.shape[:2]
                name, price, price_obj, name_objs = extract_info_heuristic(result, h)
                draw_debug(str(file_path), str(debug_dir / f"debug_{file_path.name}"), price_obj, name_objs)
            
            results.append({'filename': file_path.name, 'extracted_name': name, 'extracted_price': price})
            print(f"  -> Name: {name}\n  -> Price: {price}")
            
        except Exception as e:
            print(f"  -> Error: {e}")
            results.append({'filename': file_path.name, 'extracted_name': "ERROR", 'extracted_price': str(e)})

    csv_path = output_dir / "results.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'extracted_name', 'extracted_price'])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nDone! Results saved to {csv_path}")

if __name__ == "__main__":
    main()

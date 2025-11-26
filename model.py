from pathlib import Path
import random
from ultralytics import YOLO
import torch
import argparse
import os
import shutil
import cv2
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="YOLOv11 Training Model")
    parser.add_argument("--config", type=str, default="configs/dataset.yaml", help="Path to dataset config file")
    parser.add_argument("--num_epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--num_workers", type=int, default=4, help="Number of workers for data loading")
    parser.add_argument("--image_size", type=int, default=640, choices=[320, 640, 1280], help="Image size")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--test_grouping", action="store_true", help="Test grouping after training")
    parser.add_argument("--name", type=str, default="latest_yolo_run", help="Name of the training run")
    parser.add_argument("--optimizer", type=str, default="AdamW", choices=["SGD", "Adam", "AdamW"], help="Optimizer to use for training")
    
    # Evaluation parameters
    parser.add_argument("--eval", action="store_true", help="Run in inference mode")
    parser.add_argument("--eval_model", type=str, default="data/runs/yolo_training/latest_yolo_run/weights/best.pt", help="Path to trained model for evaluation")
    parser.add_argument("--eval_data", type=str, help="Path to folder containing images for evaluation")
    parser.add_argument("--eval_conf", type=float, default=0.25, help="Confidence threshold for evaluation")
    
    # Dataset split parameters
    parser.add_argument("--train_ratio", type=float, default=0.8, help="Ratio of training data (default: 0.8)")
    parser.add_argument("--val_ratio", type=float, default=0.1, help="Ratio of validation data (default: 0.1)")
    parser.add_argument("--test_ratio", type=float, default=0.1, help="Ratio of test data (default: 0.1)")

    # Additional training parameters
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate for training")
    parser.add_argument("--momentum", type=float, default=0.937, help="Momentum for SGD optimizer")
    parser.add_argument("--weight_decay", type=float, default=0.0005, help="Weight decay for optimizer")
    parser.add_argument("--save_period", type=int, default=10, help="Model save period every N epochs")
    parser.add_argument("--save_dir", type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "runs", "yolo_training"), help="Directory to save trained models")
    args = parser.parse_args()

    # Validate split ratios
    if not args.eval and abs(args.train_ratio + args.val_ratio + args.test_ratio - 1.0) > 1e-6:
        raise ValueError("Train, validation, and test ratios must sum to 1.0")

    print("Starting YOLOv11 training.." if not args.eval else "Starting YOLOv11 evaluation..")
    
    # Handle evaluation mode
    if args.eval:
        if not args.eval_data:
            # Default to test set if no specific data provided
            raise ValueError("--eval_data is required when using evaluation mode")
        
        evaluate_model(args.eval_model, args.eval_data, args.eval_conf)
        return
    
    # Load pretrained model (use YOLO11s for more capacity)
    model = YOLO("yolo11s.pt")
    
    # Prepare dataset from all week folders
    make_pathlists("data/originals", "configs/lists", args.train_ratio, args.val_ratio, args.test_ratio)
    

    # Start training
    results = model.train(
        data=args.config,
        epochs=args.num_epochs,
        imgsz=args.image_size,
        batch=args.batch_size,
        device='cuda' if torch.cuda.is_available() else 'cpu',
        save=True,
        save_period=args.save_period,
        workers=args.num_workers,
        lr0=args.lr,
        momentum=args.momentum,
        weight_decay=args.weight_decay,
        project=args.save_dir,
        name=args.name,
        exist_ok=True,
    )
    
    print("Training completed!")
    best_model_path = os.path.join(args.save_dir, args.name, 'weights', 'best.pt')
    print(f"Best model saved at: {best_model_path}")

def evaluate_model(model_path = "models/best.pt", data_path="", conf_threshold=0.25):
    """
    Evaluate a trained YOLO model on images and save results.
    
    Args:
        model_path (str): Path to the trained model
        data_path (str): Path to folder containing images for evaluation
        conf_threshold (float): Confidence threshold for detections
    """
    print(f"Loading model from: {model_path}")
    model = YOLO(model_path)
    
    data_dir = Path(data_path)
    if not data_dir.exists():
        raise FileNotFoundError(f"Evaluation data directory '{data_path}' does not exist")
    
    # Create evaluation results directory
    eval_results_dir = Path("eval-results")
    eval_results_dir.mkdir(exist_ok=True)
    
    # Create crops directory
    crops_dir = eval_results_dir / "crops"
    crops_dir.mkdir(exist_ok=True)
    
    # Get all image files
    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff']
    image_files = []
    for ext in image_extensions:
        image_files.extend(data_dir.glob(ext))
    
    if not image_files:
        raise ValueError(f"No image files found in '{data_path}'")
    
    print(f"Found {len(image_files)} images for evaluation")
    
    # Initialize results storage
    all_detections = []
    results_txt_path = eval_results_dir / "detections.txt"
    crop_counter = 0  # Global counter for unique crop naming

    
    # Process each image
    for i, img_path in enumerate(image_files):
        print(f"Processing {i+1}/{len(image_files)}: {img_path.name}")
        
        # Run inference
        results = model(str(img_path), conf=conf_threshold)
        
        # Load original image for drawing
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"Warning: Could not load image {img_path}")
            continue
        
        img_height, img_width = img.shape[:2]
        img_for_crops = img.copy()  # Use this for cropping, keep 'img' for drawing

        # Process detections
        image_detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for j in range(len(boxes)):
                    # Get detection info
                    class_id = int(boxes.cls[j])
                    confidence = float(boxes.conf[j])
                    
                    # Get bounding box coordinates (xyxy format)
                    x1, y1, x2, y2 = boxes.xyxy[j].cpu().numpy()
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    
                    # Get normalized coordinates (xywhn format)
                    x_center_norm = float(boxes.xywhn[j][0])
                    y_center_norm = float(boxes.xywhn[j][1])
                    width_norm = float(boxes.xywhn[j][2])
                    height_norm = float(boxes.xywhn[j][3])
                    
                    # Crop the detected product
                    crop_counter += 1
                    crop_filename = f"crop{crop_counter:03d}_{img_path.stem}.png"
                    crop_path = crops_dir / crop_filename
                    
                    # Ensure coordinates are within image bounds
                    x1_crop = max(0, x1)
                    y1_crop = max(0, y1)
                    x2_crop = min(img_width, x2)
                    y2_crop = min(img_height, y2)
                    
                    if x2_crop > x1_crop and y2_crop > y1_crop:
                        cropped_img = img_for_crops[y1_crop:y2_crop, x1_crop:x2_crop]
                        cv2.imwrite(str(crop_path), cropped_img)
                        print(f"    Saved crop: {crop_filename}")
                    
                    # Store detection info
                    detection_info = {
                        'image_name': img_path.name,
                        'image_width': img_width,
                        'image_height': img_height,
                        'class_id': class_id,
                        'confidence': confidence,
                        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,  # Absolute coordinates
                        'x_center_norm': x_center_norm,
                        'y_center_norm': y_center_norm,
                        'width_norm': width_norm,
                        'height_norm': height_norm,
                        'crop_filename': crop_filename  # Add crop filename to detection info
                    }
                    
                    image_detections.append(detection_info)
                    all_detections.append(detection_info)
                    
                    # Draw bounding box on image
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Add label with confidence
                    label = f"Product: {confidence:.2f}"
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                    cv2.rectangle(img, (x1, y1 - label_size[1] - 10), 
                                (x1 + label_size[0], y1), (0, 255, 0), -1)
                    cv2.putText(img, label, (x1, y1 - 5), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Save image with detections
        output_img_path = eval_results_dir / f"detected_{img_path.name}"
        cv2.imwrite(str(output_img_path), img)
        
        print(f"  Found {len(image_detections)} detections")
    
    # Save detections to text file
    save_detections_to_txt(results_txt_path, model_path, data_path, conf_threshold, image_files, all_detections)

    # Create summary
    summary_path = eval_results_dir / "summary.txt"
    write_evaluation_summary(summary_path, model_path, data_path, conf_threshold, image_files, all_detections)

def make_pathlists(
    originals_root: str = "data/originals",
    out_dir: str = "configs/lists",
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
):
    """
    Traverse data/originals/<shop>/<week>/ and write:
    configs/lists/train.txt, val.txt, test.txt — absolute paths to images line by
    line. Only images that have a corresponding .txt file are included.
    """
    root = Path(originals_root).resolve()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Collect all valid images (jpg/jpeg/png) that have a paired .txt
    exts = (".jpg", ".jpeg", ".png")
    imgs: list[Path] = []
    for shop_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for week_dir in sorted(p for p in shop_dir.iterdir() if p.is_dir()):
            for img in week_dir.iterdir():
                if img.suffix.lower() in exts:
                    lbl = img.with_suffix(".txt")
                    if lbl.exists():
                        imgs.append(img.resolve())

    if not imgs:
        raise RuntimeError(f"No image/label pairs under {root}")

    # Stable split
    rng = random.Random(seed)
    rng.shuffle(imgs)
    n = len(imgs)
    n_tr = int(n * train_ratio)
    n_va = int(n * val_ratio)
    splits = {
        "train": imgs[:n_tr],
        "val":   imgs[n_tr:n_tr + n_va],
        "test":  imgs[n_tr + n_va:],
    }

    # Write lists (as_posix to use / on Windows)
    for split, arr in splits.items():
        with open(out / f"{split}.txt", "w", encoding="utf-8") as f:
            for p in arr:
                f.write(p.as_posix() + "\n")

    print("Pathlists written:", {k: len(v) for k, v in splits.items()})
    return out / "train.txt", out / "val.txt", out / "test.txt"

def write_evaluation_summary(summary_path, model_path, data_path, conf_threshold, image_files, all_detections):
    """
    Write a summary of the evaluation results.
    
    Args:
        summary_path (Path): Path to save the summary file
        model_path (str): Path to the trained model
        data_path (str): Path to the evaluation data
        conf_threshold (float): Confidence threshold used for evaluation
        image_files (list): List of image files processed
        all_detections (list): List of all detections made
    """
    with open(summary_path, 'w') as f:
        f.write("EVALUATION SUMMARY\n")
        f.write("=" * 50 + "\n")
        f.write(f"Model: {model_path}\n")
        f.write(f"Data: {data_path}\n")
        f.write(f"Confidence threshold: {conf_threshold}\n")
        f.write(f"Total images processed: {len(image_files)}\n")
        f.write(f"Total detections: {len(all_detections)}\n")
        
        # Confidence distribution
        if all_detections:
            confidences = [d['confidence'] for d in all_detections]
            f.write(f"Confidence - Min: {min(confidences):.3f}, Max: {max(confidences):.3f}, "
                   f"Mean: {sum(confidences)/len(confidences):.3f}\n")
        
        f.write(f"\nResults saved in: {summary_path.parent.absolute()}\n")
        f.write("- detected_*.png: Images with bounding boxes drawn\n")
        f.write("- detections.txt: All detection data in CSV format\n")
        f.write("- summary.txt: This summary file\n")

def save_detections_to_txt(results_txt_path, model_path, data_path, conf_threshold, image_files, all_detections):
    """
    Save all detection results to a text file.
    
    Args:
        results_txt_path (Path): Path to save the results text file
        model_path (str): Path to the trained model
        data_path (str): Path to the evaluation data
        conf_threshold (float): Confidence threshold used for evaluation
        image_files (list): List of image files processed
        all_detections (list): List of all detections made
    """
    print(f"Saving detection results to: {results_txt_path}")
    with open(results_txt_path, 'w') as f:
        # Write header
        f.write("# YOLO Model Evaluation Results\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Model: {model_path}\n")
        f.write(f"# Data: {data_path}\n")
        f.write(f"# Confidence threshold: {conf_threshold}\n")
        f.write(f"# Total images processed: {len(image_files)}\n")
        f.write(f"# Total detections: {len(all_detections)}\n")
        f.write("#\n")

if __name__ == "__main__":
    main()

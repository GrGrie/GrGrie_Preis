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
    
    # Evaluation parameters
    parser.add_argument("--eval", action="store_true", help="Run in inference mode")
    parser.add_argument("--eval_model", type=str, default="runs/detect/latest_yolo_run/weights/best.pt", help="Path to trained model for evaluation")
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
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience")
    parser.add_argument("--save_period", type=int, default=10, help="Model save period every N epochs")
    parser.add_argument("--save_dir", type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "runs", "yolo_training"), help="Directory to save trained models")
    args = parser.parse_args()

    # Validate split ratios
    if not args.eval and abs(args.train_ratio + args.val_ratio + args.test_ratio - 1.0) > 1e-6:
        raise ValueError("Train, validation, and test ratios must sum to 1.0")

    print("Starting YOLOv11 training.." if not args.eval else "Starting YOLOv11 evaluation..")
    print(f"Using dataset config: {args.config}")
    
    # Handle evaluation mode
    if args.eval:
        if not args.eval_data:
            # Default to test set if no specific data provided
            raise ValueError("--eval_data is required when using evaluation mode")
        
        evaluate_model(args.eval_model, args.eval_data, args.eval_conf)
        return

    # Prepare dataset from all week folders
    prepare_global_dataset(args.train_ratio, args.val_ratio, args.test_ratio)

    # Load pretrained model
    model = YOLO("yolo11m.pt")

    # Start training
    results = model.train(
        data=args.config,
        epochs=args.num_epochs,
        imgsz=args.image_size,
        batch=args.batch_size,
        device='cuda' if torch.cuda.is_available() else 'cpu',
        patience=args.patience,
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

def evaluate_model(model_path = "runs/detect/latest_yolo_run/weights/best.pt", data_path="", conf_threshold=0.25):
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

def prepare_global_dataset(train_ratio, val_ratio, test_ratio):
    """
    Aggregate all data from week folders and create global train/val/test split.
    Only class 5 (Product) labels are kept and converted to class 0.
    
    Args:
        train_ratio (float): Ratio of training data
        val_ratio (float): Ratio of validation data  
        test_ratio (float): Ratio of test data
    """
    print("Preparing global dataset...")
    
    originals_dir = Path("data/originals")
    if not originals_dir.exists():
        raise FileNotFoundError(f"Directory '{originals_dir}' does not exist.")
    
    # Collect all image-label pairs from all week folders
    all_image_label_pairs = []
    
    # Find all subdirectories (lidl, netto, etc.)
    subdirectories = [d for d in originals_dir.iterdir() if d.is_dir()]

    print(f"Found {len(subdirectories)} subdirectories: {subdirectories}")

    for subdir in subdirectories:
        # Find all week folders (without _labels suffix)
        week_folders = [
            name for name in os.listdir(subdir) 
            if subdir.joinpath(name).is_dir() and not name.endswith("_labels")
        ]
        
        print(f"Found {len(week_folders)} week folders in '{subdir.name}': {week_folders}")
        
        for week in week_folders:
            week_path = subdir / week
            labels_path = subdir / f"{week}_labels"
            
            if not week_path.exists():
                print(f"Warning: Week folder '{week_path}' does not exist. Skipping.")
                continue
                
            if not labels_path.exists():
                print(f"Warning: Labels folder '{labels_path}' does not exist. Skipping {week}.")
                continue
            
            # Get all PNG images in the week folder
            images = list(week_path.glob("*.png"))
            print(f"Week {week}: Found {len(images)} images")
            
            # Check for corresponding labels
            valid_pairs = 0
            for img_path in images:
                label_path = labels_path / f"{img_path.stem}.txt"
                if label_path.exists():
                    # Check if the label file contains class 5 (Product)
                    if has_product_class(label_path):
                        all_image_label_pairs.append((img_path, label_path))
                        valid_pairs += 1
            
            print(f"Week {week}: {valid_pairs} valid image-label pairs with Product class")
    
    if not all_image_label_pairs:
        raise ValueError("No valid image-label pairs found with Product class (class 5)")
    
    print(f"Total valid image-label pairs: {len(all_image_label_pairs)}")
    
    # Shuffle and split the data
    random.shuffle(all_image_label_pairs)
    
    total_samples = len(all_image_label_pairs)
    train_end = int(train_ratio * total_samples)
    val_end = train_end + int(val_ratio * total_samples)
    
    train_pairs = all_image_label_pairs[:train_end]
    val_pairs = all_image_label_pairs[train_end:val_end]
    test_pairs = all_image_label_pairs[val_end:]
    
    print(f"Dataset split: Train={len(train_pairs)}, Val={len(val_pairs)}, Test={len(test_pairs)}")
    
    # Create output directories
    data_dir = Path("data")
    for split in ["train", "val", "test"]:
        for subdir in ["images", "labels"]:
            output_dir = data_dir / split / subdir
            output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy files to respective directories
    for split_name, pairs in [("train", train_pairs), ("val", val_pairs), ("test", test_pairs)]:
        print(f"Copying {len(pairs)} files to {split_name} set...")
        
        for img_path, label_path in pairs:
            # Make unique filename by prefixing with week folder name
            week_prefix = img_path.parent.name  # e.g., '2025-06-09_2025-06-15'
            unique_img_name = f"{week_prefix}_{img_path.name}"
            unique_label_name = f"{week_prefix}_{label_path.name}"

            # Copy image
            img_dest = data_dir / split_name / "images" / unique_img_name
            shutil.copy2(img_path, img_dest)

            # Process and copy label (filter only class 5 and convert to class 0)
            label_dest = data_dir / split_name / "labels" / unique_label_name
            process_label_file(label_path, label_dest)
    
    print("Dataset preparation completed!")
    print(f"Data organized in:")
    print(f"  - /data/train: {len(train_pairs)} samples")
    print(f"  - /data/val: {len(val_pairs)} samples") 
    print(f"  - /data/test: {len(test_pairs)} samples")

def has_product_class(label_path):
    """
    Check if a label file contains class 5 (Product).
    
    Args:
        label_path (Path): Path to the label file
        
    Returns:
        bool: True if class 5 is present, False otherwise
    """
    try:
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if parts and parts[0] == "5":
                    return True
        return False
    except Exception as e:
        print(f"Error reading label file {label_path}: {e}")
        return False

def process_label_file(input_path, output_path):
    """
    Process a label file to keep only class 5 (Product) and convert it to class 0.
    
    Args:
        input_path (Path): Input label file path
        output_path (Path): Output label file path
    """
    try:
        with open(input_path, 'r') as fin, open(output_path, 'w') as fout:
            for line in fin:
                parts = line.strip().split()
                if parts and parts[0] == "5":
                    # Convert class 5 to class 0 for single-class training
                    fout.write("0 " + " ".join(parts[1:]) + "\n")
    except Exception as e:
        print(f"Error processing label file {input_path}: {e}")

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
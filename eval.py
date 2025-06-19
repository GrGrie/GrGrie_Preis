# Model Evaluation and Testing Script

from ultralytics import YOLO
import cv2
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
import argparse

def evaluate_model(model_path):
    
    model = YOLO(model_path)
    
    print("=== MODEL EVALUATION ===")
    
    # 1. Check training results (automatically generated during training)
    results_dir = Path(model_path).parent.parent  # Go up to the experiment folder
    
    # Training plots should be in the same directory as weights
    plots_to_check = [
        'results.png',      # Training/validation curves
        'confusion_matrix.png',  # Confusion matrix
        'PR_curve.png',     # Precision-Recall curve
        'F1_curve.png',     # F1 score curve
    ]
    
    print(f"Check these plots in: {results_dir}")
    for plot in plots_to_check:
        plot_path = results_dir / plot
        if plot_path.exists():
            print(f"✓ {plot} - Available")
        else:
            print(f"✗ {plot} - Not found")
    
    # 2. Validate on validation set
    print("\n=== VALIDATION METRICS ===")
    val_results = model.val(data='dataset.yaml')
    
    print(f"mAP50: {val_results.box.map50:.3f}")  # Mean Average Precision at IoU 0.5
    print(f"mAP50-95: {val_results.box.map:.3f}")  # Mean Average Precision at IoU 0.5-0.95
    print(f"Precision: {val_results.box.mp:.3f}")
    print(f"Recall: {val_results.box.mr:.3f}")
    
    return model

def test_on_new_images(model, test_images_dir, save_dir="test_results"):
    """Test model on new images and visualize results"""
    
    test_images_path = Path(test_images_dir)
    save_path = Path(save_dir)
    save_path.mkdir(exist_ok=True)
    
    # Get all image files
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
    test_images = []
    for ext in image_extensions:
        test_images.extend(test_images_path.glob(ext))
    
    print(f"\n=== TESTING ON {len(test_images)} NEW IMAGES ===")

    for img_path in test_images:
        print(f"Testing: {img_path.name}")
        
        # Run inference
        results = model(str(img_path), conf=0.25)  # Confidence threshold
        
        # Save annotated image
        for i, result in enumerate(results):
            # Save the annotated image
            annotated_img = result.plot()
            output_path = save_path / f"annotated_{img_path.name}"
            cv2.imwrite(str(output_path), annotated_img)
            
            # Print detections info and save bounding boxes
            boxes = result.boxes
            if boxes is not None:
                print(f"  Found {len(boxes)} products")
                for box in boxes:
                    conf = box.conf[0].item()
                    cls = int(box.cls[0].item())
                    class_name = model.names[cls] if hasattr(model, "names") else str(cls)
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    print(f"    {class_name} (confidence: {conf:.2f}) bbox=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f})")
                # Save bounding boxes to text file
                output_txt_path = save_path / "all_bboxes.txt"
                append_bboxes_to_txt(output_txt_path, boxes, model, img_path.name)
            else:
                print("  No products detected")
    
    print(f"Annotated images saved in: {save_path}")

def interactive_test(model):
    """Interactive testing - input image path and see results"""
    
    print("\n=== INTERACTIVE TESTING ===")
    print("Enter image paths to test (or 'quit' to exit):")
    
    while True:
        img_path = input("Image path: ").strip()
        
        if img_path.lower() == 'quit':
            break
            
        if not Path(img_path).exists():
            print("File not found! Try again.")
            continue
        
        # Run inference
        results = model(img_path, conf=0.25)
        
        # Display results
        for result in results:
            # Show image with detections
            result.show()  # This will display the image
            
            # Print detection details
            boxes = result.boxes
            if boxes is not None:
                print(f"Detected {len(boxes)} products:")
                for i, box in enumerate(boxes):
                    conf = box.conf[0].item()
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    # print(f"  Product {i+1}: confidence={conf:.2f}, bbox=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f})")
            else:
                print("No products detected")

def check_model_performance_indicators(model_path):
    """Quick performance check indicators"""
    results_dir = Path(model_path).parent / "results"
    if results_dir.exists():
        print(f"Results directory found: {results_dir}")
    else:
        print(f"Results directory not found: {results_dir}")

def append_bboxes_to_txt(output_txt_path, boxes, model, image_name):
    with open(output_txt_path, "a") as f:
        for box in boxes:
            conf = box.conf[0].item()
            cls = int(box.cls[0].item())
            class_name = model.names[cls] if hasattr(model, "names") else str(cls)
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            # Save as: image_name, class_name, confidence, x1, y1, x2, y2
            f.write(f"{image_name} {class_name} {conf:.4f} {x1:.0f} {y1:.0f} {x2:.0f} {y2:.0f}\n")

def main():
    parser = argparse.ArgumentParser(description="Evaluate YOLOv11 Model")
    parser.add_argument("--model_path", type=str, default="runs/detect/lidl_products_v1/weights/best.pt", help="Path to the trained YOLOv11 model weights")
    parser.add_argument("--test_dir", type=str, default="./data/test", help="Directory containing test images")

    args = parser.parse_args()

    model_path = args.model_path

    # 1. Load and evaluate model
    model = evaluate_model(model_path)
    
    # 2. Check performance indicators
    check_model_performance_indicators(model_path)
    
    # 3. Test on new images (update path to your test images)
    test_on_new_images(model, args.test_dir)

    # 4. Interactive testing
    # interactive_test(model)


if __name__ == "__main__":
    main()
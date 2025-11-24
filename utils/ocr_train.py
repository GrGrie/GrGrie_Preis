"""
Enhanced YOLO training script with YOLOv11s and strong augmentation. Output model is used for OCR pipeline.
"""
from ultralytics import YOLO
import argparse
import shutil
from pathlib import Path
import yaml 
import random

def setup_dataset(source_dir, split_ratio=0.8):
    """Setup dataset with train/val split"""
    source_path = Path(source_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"Source directory {source_dir} not found")

    # Create temp dataset structure
    dataset_dir = Path("temp_dataset")
    if dataset_dir.exists():
        shutil.rmtree(dataset_dir)
    
    dirs = {
        'train_img': dataset_dir / 'train' / 'images',
        'train_lbl': dataset_dir / 'train' / 'labels',
        'val_img': dataset_dir / 'val' / 'images',
        'val_lbl': dataset_dir / 'val' / 'labels'
    }
    
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # Get all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
    images = [f for f in source_path.iterdir() if f.suffix.lower() in image_extensions]
    
    # Filter images that have corresponding labels
    valid_pairs = []
    for img in images:
        lbl = img.with_suffix('.txt')
        if lbl.exists():
            valid_pairs.append((img, lbl))
    
    if not valid_pairs:
        raise ValueError(f"No valid image-label pairs found in {source_dir}")

    print(f"Found {len(valid_pairs)} valid image-label pairs")
    
    # Shuffle and split
    random.seed(42)  # For reproducibility
    random.shuffle(valid_pairs)
    split_idx = int(len(valid_pairs) * split_ratio)
    train_pairs = valid_pairs[:split_idx]
    val_pairs = valid_pairs[split_idx:]
    
    # Copy files
    def copy_pairs(pairs, img_dest, lbl_dest):
        for img, lbl in pairs:
            shutil.copy2(img, img_dest / img.name)
            shutil.copy2(lbl, lbl_dest / lbl.name)
            
    copy_pairs(train_pairs, dirs['train_img'], dirs['train_lbl'])
    copy_pairs(val_pairs, dirs['val_img'], dirs['val_lbl'])
    
    print(f"Split: {len(train_pairs)} train, {len(val_pairs)} val")
    
    # Create data.yaml
    data_yaml = {
        'path': str(dataset_dir.absolute()),
        'train': 'train/images',
        'val': 'val/images',
        'nc': 2,
        'names': ['Name', 'Price']
    }
    
    yaml_path = dataset_dir / 'data.yaml'
    with open(yaml_path, 'w') as f:
        yaml.dump(data_yaml, f)
        
    return yaml_path

def main():
    parser = argparse.ArgumentParser(description="Train Enhanced YOLO Layout Detection Model")
    parser.add_argument("--source", type=str, required=True, help="Path to directory with images and labels")
    parser.add_argument("--epochs", type=int, default=200, help="Number of epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--name", type=str, default="yolo_layout_enhanced", help="Run name")
    parser.add_argument("--model", type=str, default="yolo11s.pt", help="Base model (yolo11s.pt recommended)")
    parser.add_argument("--lr", type=float, default=0.01, help="Learning rate")
    args = parser.parse_args()

    try:
        # Setup dataset
        print("Setting up dataset...")
        data_yaml_path = setup_dataset(args.source)
        
        # Load model
        print(f"Loading model: {args.model}")
        model = YOLO(args.model)

        # Train with enhanced augmentation
        print(f"Starting training with enhanced augmentation...")
        results = model.train(
            data=str(data_yaml_path),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            name=args.name,
            project="runs/detect",
            exist_ok=True,
            lr0=args.lr,
            # Enhanced augmentation parameters
            hsv_h=0.015,      # Hue augmentation
            hsv_s=0.7,        # Saturation
            hsv_v=0.4,        # Value (brightness)
            degrees=5.0,      # Rotation (±5 degrees)
            translate=0.1,    # Translation (10%)
            scale=0.5,        # Scaling (±50%)
            shear=2.0,        # Shear (±2 degrees)
            perspective=0.0,  # Perspective transform (0 for text)
            flipud=0.0,       # Vertical flip (0 for text)
            fliplr=0.5,       # Horizontal flip (50% chance)
            mosaic=1.0,       # Mosaic augmentation
            mixup=0.1,        # Mixup augmentation
            # Training parameters
            patience=50,      # Early stopping patience
            save=True,
            save_period=10,   # Save checkpoint every 10 epochs
            plots=True,       # Save training plots
            verbose=True
        )

        # Get best model path
        best_model_path = Path("runs/detect") / args.name / "weights" / "best.pt"
        
        # Export to ONNX
        print("\nExporting best model to ONNX...")
        best_model = YOLO(str(best_model_path))
        onnx_path = best_model.export(format="onnx", dynamic=True, simplify=True)
        print(f"ONNX model exported to: {onnx_path}")
        
        # Copy to models/ocr/
        output_dir = Path("models/ocr")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup old model
        old_onnx = output_dir / "best.onnx"
        if old_onnx.exists():
            backup_path = output_dir / "best_backup.onnx"
            shutil.copy2(old_onnx, backup_path)
            print(f"Backed up old model to: {backup_path}")
        
        # Copy new model
        shutil.copy2(onnx_path, old_onnx)
        print(f"New model saved to: {old_onnx}")
        
        # Also save .pt model
        shutil.copy2(best_model_path, output_dir / "best.pt")
        print(f"PyTorch model saved to: {output_dir / 'best.pt'}")
        
        print("\n✓ Training complete!")
        print(f"✓ Best model: {best_model_path}")
        print(f"✓ ONNX model: {old_onnx}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\nDataset prepared in: temp_dataset")
        print(f"Training results in: runs/detect/{args.name}")

if __name__ == "__main__":
    main()

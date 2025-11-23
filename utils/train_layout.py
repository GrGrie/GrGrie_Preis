from ultralytics import YOLO
import argparse
import os
import shutil
import random
import yaml
from pathlib import Path

def setup_dataset(source_dir, split_ratio=0.8):
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
        'names': ['product_name', 'price_tag']
    }
    
    yaml_path = dataset_dir / 'data.yaml'
    with open(yaml_path, 'w') as f:
        yaml.dump(data_yaml, f)
        
    return yaml_path

def main():
    parser = argparse.ArgumentParser(description="Train YOLO Layout Detection Model")
    parser.add_argument("--source", type=str, required=True, help="Path to directory with images and labels")
    parser.add_argument("--epochs", type=int, default=50, help="Number of epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--name", type=str, default="yolo_layout", help="Run name")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Base model")
    args = parser.parse_args()

    try:
        # Setup dataset
        print("Setting up dataset...")
        data_yaml_path = setup_dataset(args.source)
        
        # Load model
        model = YOLO(args.model)

        # Train
        print(f"Starting training using {data_yaml_path}...")
        results = model.train(
            data=str(data_yaml_path),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            name=args.name,
            project="runs/detect",
            exist_ok=True
        )

        # Export to ONNX
        print("Exporting to ONNX...")
        success = model.export(format="onnx", dynamic=True)
        print(f"Export success: {success}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup temp dataset? Maybe keep it for inspection.
        print(f"Dataset prepared in: temp_dataset")

if __name__ == "__main__":
    main()

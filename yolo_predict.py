# simple_train.py - Quick YOLOv11 training script

from ultralytics import YOLO
import torch
def main():
    print("Starting YOLOv11 training...")
    print(f"Using PyTorch version: {torch.__version__}")
    print(f"Using CUDA: {torch.cuda.is_available()}")
    # Load pretrained model
    model = YOLO('yolo11n.pt')  # Downloads automatically if not present
    model.to('cuda' if torch.cuda.is_available() else 'cpu')  # Use GPU if available
    
    # Start training
    results = model.train(
        data='dataset.yaml',        # Your dataset config file
        epochs=5,                   # Start with fewer epochs for testing
        imgsz=640,                  # Image size
        batch=16,                   # Small batch size for CPU/limited GPU
        #device='cuda',              # CUDA for GPU training, change to 'cpu' if no GPU available
        patience=10,                # Early stopping
        save=True,
        plots=True,
        name='lidl_products_v1'
    )
    
    print("Training completed!")
    print(f"Best model saved at: runs/detect/lidl_products_v1/weights/best.pt")

if __name__ == "__main__":
    main()
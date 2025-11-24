from ultralytics import YOLO
from huggingface_hub import snapshot_download

def export_model_to_onnx():
    # Load the trained YOLO model
    model = YOLO("models/best.pt")

    # Export the model to ONNX format
    model.export(format="onnx", imgsz=640, dynamic=True, simplify=True, half=False, device="cpu", optimize=False)

    print("Exported models/best.pt to models/best.onnx")

def download_ocr_model():
    local_dir = "models/ocr/latin_PP-OCRv5_mobile_rec"
    snapshot_download(
        repo_id="PaddlePaddle/latin_PP-OCRv5_mobile_rec",
        local_dir=local_dir,
        local_dir_use_symlinks=False, 
        allow_patterns=["*inference*", "*.txt", "*.json"]  # Download only inference model files and keys.txt
    )
    print("Saved to:", local_dir)

def main():
    download_ocr_model()

if __name__ == "__main__":
    main()
    

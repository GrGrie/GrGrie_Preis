from ultralytics import YOLO

def export_model_to_onnx():
    # Load the trained YOLO model
    model = YOLO("models/best.pt")

    # Export the model to ONNX format
    model.export(format="onnx", imgsz=640, dynamic=True, simplify=True, half=False, device="cpu", optimize=False)

    print("Exported models/best.pt to models/best.onnx")

def main():
    export_model_to_onnx()
    
if __name__ == "__main__":
    main()
    

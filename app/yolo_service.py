from io import BytesIO
from PIL import Image
from ultralytics import YOLO

MODEL_PATH = "models/best.onnx"

class YoloService:
    def __init__(self, conf: float = 0.25):
        self.model = YOLO(MODEL_PATH)
        self.conf = conf

    def predict_image_bytes(self, data: bytes, conf: float | None = None):
        img = Image.open(BytesIO(data)).convert("RGB")
        results = self.model(img, conf=self.conf if conf is None else conf)
        dets = []
        for r in results:
            if r.boxes is None: continue
            for b in r.boxes:
                x1,y1,x2,y2 = map(int, b.xyxy[0].tolist())
                dets.append({"class_id": int(b.cls), "score": float(b.conf), "box": [x1,y1,x2,y2]})
        return dets
    
    def predict_pil(self, img: Image.Image, conf: float | None = None):
        results = self.model(img, conf=self.conf if conf is None else conf)
        dets = []
        for r in results:
            if r.boxes is None: continue
            for b in r.boxes:
                x1,y1,x2,y2 = map(int, b.xyxy[0].tolist())
                dets.append({"class_id": int(b.cls), "score": float(b.conf), "box": [x1,y1,x2,y2]})
        return dets

import os, sys, json, time, uuid, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from ultralytics import YOLO
from app.ocr import ocr_folder


#  Directory to save inference results (images with boxes, labels, etc.)
RUNS_DIR = Path(os.getenv("RUNS_DIR", "static/runs")).resolve()
DATA_ORIGINALS = Path(os.getenv("DATA_ORIGINALS", "static")).resolve()
MODEL_PATH = "models/best.onnx"

class YoloService:
    def __init__(self, conf: float = 0.25):
        self.conf = conf
        self.model = YOLO(MODEL_PATH)
        self.model.task = "detect"
    
    def predict_pil(self, img: Image.Image, conf: float | None = None):
        results = self.model(img, conf=self.conf if conf is None else conf)
        dets = []
        for r in results:
            if r.boxes is None: continue
            for b in r.boxes:
                x1,y1,x2,y2 = map(int, b.xyxy[0].tolist())
                dets.append({"class_id": int(b.cls), "score": float(b.conf), "box": [x1,y1,x2,y2]})
        return dets

def _new_run_dir() -> Path:
    """Create a new unique run directory and return its Path"""
    run_id = time.strftime("%Y-%m-%d_%H-%M-%S_") + uuid.uuid4().hex[:6]
    rd = RUNS_DIR / run_id
    (rd / "crops").mkdir(parents=True, exist_ok=True)
    return rd

def _get_this_week_monday() -> str:
    """Get the date string (YYYY-MM-DD) for this week's Monday"""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")

def _get_this_week_saturday() -> str:
    """Get the date string (YYYY-MM-DD) for this week's Saturday"""
    today = datetime.now()
    saturday = today + timedelta((5 - today.weekday()) % 7)
    return saturday.strftime("%Y-%m-%d")

THIS_MONDAY = _get_this_week_monday()
THIS_SATURDAY = _get_this_week_saturday()

def _scraped_dir_exists(directory_to_check: Path) -> bool:
    """Check if the scraped pages directory contains this week's scraped images."""
    for d in directory_to_check.iterdir():
        if d.is_dir() and d.name.startswith(THIS_MONDAY):
            jpg_files = list(d.glob("*.jpg"))
            if len(jpg_files) > 0:
                return True
    return False

def _try_call_scraper(site: str, out_dir: Path, num_prospekt: int) -> bool:
    """Call the scraper subprocess to download images if not already done for this week."""
    cmd = [sys.executable, "scrape.py",
           "--site", site,
           "--download-path", str(out_dir),
           "--num_prospekt", str(num_prospekt)]
    try:
        if not _scraped_dir_exists(out_dir):
            subprocess.run(cmd, check=True)
        return True
    except Exception:
        
        return False

def run_once(site: str = "lidl", conf: float = 0.25, num_prospekt: int = 1) -> dict:
    run_dir   = _new_run_dir()
    pages_dir = DATA_ORIGINALS / site
    crops_dir = run_dir / "crops"

    # 1) Scrape PNG pages for the given site and prospekt
    _try_call_scraper(site, pages_dir, num_prospekt)

    # 2) Run YOLO and save crops
    yolo = YoloService(conf=conf)
    items = []
    pages_dir = pages_dir / f"{THIS_MONDAY}_{THIS_SATURDAY}"  # only this week's pages
    for i, page_path in enumerate(sorted(pages_dir.glob("*.jpg")), 1):
        img = Image.open(page_path).convert("RGB")
        dets = yolo.predict_pil(img, conf=conf)
        for j, d in enumerate(dets, 1):
            x1, y1, x2, y2 = d["box"]
            crop = img.crop((x1, y1, x2, y2))
            name = f"p{i:02d}_b{j:03d}.jpg"
            outp = crops_dir / name
            crop.save(outp, "JPEG", quality=90)
            items.append({
                "page": i,
                "file": f"/static/runs/{run_dir.name}/crops/{name}",
                "class_id": d["class_id"],
                "score": d["score"],
                "box": d["box"]
            })

     # NEW: OCR over crops
    ocr_json = run_dir / "ocr.json"
    ocr_csv  = run_dir / "ocr.csv"
    ocr_info = ocr_folder(crops_dir, ocr_json, ocr_csv)

    meta = {"run_id": run_dir.name, "site": site, "count": len(items), "items": items,
            "ocr": ocr_info}
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta

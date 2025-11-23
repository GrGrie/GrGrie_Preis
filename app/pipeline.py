import shutil
import os, sys, json, time, uuid, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from fastapi import requests
import requests as req
from ultralytics import YOLO
import numpy as np
import onnxruntime as ort

from app.ocr import PaddleOcrService


#  Directory to save inference results (images with boxes, labels, etc.)
RUNS_DIR = Path(os.getenv("RUNS_DIR", "static/runs")).resolve()
DATA_ORIGINALS = Path(os.getenv("DATA_ORIGINALS", "static")).resolve()
MODEL_PATH = "models/best.onnx"
OCR_API_KEY = "K83109457288957"

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

def _last_modified_directory(parent_dir: Path) -> Path | None:
    """Get the most recently modified subdirectory inside parent_dir"""
    if not parent_dir.exists():
        return None
    dirs = [d for d in parent_dir.iterdir() if d.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda d: d.stat().st_mtime)

def copy_directory(source_dir: str, destination_dir: str):
    """
    Copy entire directory from source to destination
    """
    try:
        # Convert to Path objects for better handling
        src = Path(source_dir)
        dst = Path(destination_dir)
        
        # Check if source directory exists
        if not src.exists():
            print(f"[DEBUG] [pipeline] Source directory '{source_dir}' does not exist")
            return False
            
        # Copy the entire directory tree
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"[INFO] [pipeline] Successfully copied '{source_dir}' to '{destination_dir}'")
        return True
        
    except Exception as e:
        print(f"[ERROR] [pipeline] Error copying directory: {e}")
        return False
    
THIS_MONDAY = _get_this_week_monday()
THIS_SATURDAY = _get_this_week_saturday()

def _scraped_dir_exists(directory_to_check: Path) -> bool:
    """Check if the scraped pages directory contains this week's scraped images."""
    if not directory_to_check.exists():
        return False
    for d in directory_to_check.iterdir():
        if d.is_dir() and d.name.startswith(THIS_MONDAY):
            jpg_files = list(d.glob("*.jpg"))
            if len(jpg_files) > 0:
                return True
        else:
            print(f"[DEBUG] [pipeline] Ignoring directory '{d}' (not a dir or not this week's).")
            continue

    print(f"[DEBUG] [pipeline] Ended search unsuccessfully")
    return False

def _try_call_scraper(site: str, output_dir: Path) -> bool:
    """Call the scraper subprocess to download images if not already done for this week."""
    print(f"[INFO] [pipeline] Scraping pages for site '{site}' into '{output_dir}'...")
    cmd = [sys.executable, "scrape.py",
           "--site", site,
           "--download-path", str(output_dir)]
    try:
        if not _scraped_dir_exists(output_dir):
            print(f"[INFO] [pipeline] No existing scraped data for this week found. Running scraper...")
            subprocess.run(cmd, check=True)
        return True
    except Exception as e:
        print(f"[ERROR] [pipeline] Failed to run scraper: {e}")
        return False

def run_once(site: str = "lidl", conf: float = 0.25) -> dict:
    run_dir   = _new_run_dir()
    pages_dir = DATA_ORIGINALS / site
    crops_dir = run_dir / "crops"

    # 1) Scrape PNG pages for the given site and prospekt
    _try_call_scraper(site, DATA_ORIGINALS)

    # 2) Run YOLO and save crops
    yolo = YoloService(conf=conf)
    items = []
    pages_dir = _last_modified_directory(DATA_ORIGINALS)
    from app.ocr import OcrService
    for i, page_path in enumerate(sorted(pages_dir.glob("*.jpg")), 1):
        img = Image.open(page_path).convert("RGB")
        dets = yolo.predict_pil(img, conf=conf)
        for j, d in enumerate(dets, 1):
            x1, y1, x2, y2 = d["box"]
            crop = img.crop((x1, y1, x2, y2))
            name = f"p{i:02d}_b{j:03d}.jpg"
            outp = crops_dir / name
            crop.save(outp, "JPEG", quality=90)
            print(f"[INFO] [pipeline] Saved crop: {outp}, running OCR...")
            ocr_result = PaddleOcrService.infer(crop)
            items.append({
                "page": i,
                "file": f"/static/runs/{run_dir.name}/crops/{name}",
                "class_id": d["class_id"],
                "score": d["score"],
                "box": d["box"],
                "ocr": ocr_result
            })

     # NEW: OCR over crops
    ocr_json = run_dir / "ocr.json"
    ocr_csv  = run_dir / "ocr.csv"

    meta = {"run_id": run_dir.name, "site": site, "count": len(items), "items": items}
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta

def scrape_only(site: str = "lidl") -> dict:
    """
    Scrape pages for the given site without running inference.
    Saves a minimal meta.json into a fresh run folder so the /done/{run_id}
    page can display/redirect uniformly.
    """
    run_dir = _new_run_dir()

    _try_call_scraper(site, DATA_ORIGINALS)
    copy_directory(DATA_ORIGINALS / site, run_dir)

    # minimal meta so /done/{run_id} works consistently
    meta = {
        "run_id": run_dir.name,
        "site": site,
        "count": 0,
        "items": [],
        "mode": "scrape_only"
    }
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta

def crop_only(site: str = "lidl", conf: float = 0.25) -> dict:
    """
    Run cropping only on the latest , without scraping new pages.
    Saves updated meta.json with count/items/ocr.
    """
    latest_run = _last_modified_directory(RUNS_DIR)
    run_dir = _last_modified_directory(latest_run)

    # Run YOLO and save crops
    yolo = YoloService(conf=conf)
    items = []
    print(f"[INFO] [pipeline] Running YOLO on pages in '{run_dir}':")
    for i, page_path in enumerate(sorted(run_dir.glob("*.jpg")), 1):
        img = Image.open(page_path).convert("RGB")
        print(f"[INFO] [pipeline]  Found page: {page_path.name} ({img.width}x{img.height})")
        dets = yolo.predict_pil(img)
        for j, d in enumerate(dets, 1):
            x1, y1, x2, y2 = d["box"]
            if x2 <= x1 or y2 <= y1:
                print(f"[WARN] Skip empty crop: {x1},{y1},{x2},{y2}")
                continue
            crop = img.crop((x1, y1, x2, y2))
            if crop.width == 0 or crop.height == 0:
                print(f"[WARN] Skip zero-size crop after PIL: {x1},{y1},{x2},{y2}")
                continue
            name = f"p{i:02d}_b{j:03d}.jpg"
            if not (latest_run / "crops").exists():
                (latest_run / "crops").mkdir(parents=True, exist_ok=True)
            outp = latest_run / "crops" / name
            crop.save(outp, "JPEG", quality=90)
            items.append({
                "page": i,
                "file": f"/static/runs/{latest_run.name}/crops/{name}",
                "class_id": d["class_id"],
                "score": d["score"],
                "box": d["box"]
            })

     # NEW: OCR over crops
    meta_path = latest_run / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    print(f"[INFO] [pipeline] Found {len(items)} items after cropping in run {latest_run.name}, run_id {latest_run.name[-6:]}")
    meta.update({
        "count": len(items),
        "items": items,
        "mode": "crop_only",
        "run_id": latest_run.name[-6:]
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta

def ocr_latest_run() -> dict:
    """
    Run OCR only on the latest run, without scraping or cropping.
    Saves updated meta.json with count/items/ocr.
    """
    run_dir = _last_modified_directory(RUNS_DIR)
    if run_dir is None:
        raise RuntimeError("No runs found to OCR")

    crops_dir = run_dir / "crops"
    if not crops_dir.exists():
        raise RuntimeError(f"No crops directory found in latest run: {run_dir.name}")

    # NEW: OCR over crops
    ocr_json = run_dir / "ocr.json"
    print(f"[INFO] [pipeline] Running OCR on crops in '{crops_dir}':")
    
    # Initialize OCR results list
    ocr_results = []
    
    # Process each crop file in the crops directory
    for crop_file in sorted(crops_dir.glob("*.jpg")):
        print(f"[INFO] [pipeline] Processing OCR for: {crop_file.name}")
        try:
            #print(f"[INFO] [pipeline] Sending {crop_file.name} to OCR.space API. It's type is {type(crop_file.name)}")
            ocr_result = PaddleOcrService.infer(crop_file)
            # Parse the JSON response and append to results
            ocr_data = json.loads(ocr_result)
            ocr_results.append({
                "filename": crop_file.name,
                "ocr_result": ocr_data
            })
        except Exception as e:
            print(f"[ERROR] [pipeline] OCR failed for {crop_file.name}: {e}")
            ocr_results.append({
                "filename": crop_file.name,
                "error": str(e)
            })
    
    # Write all OCR results to ocr.json
    ocr_json.write_text(json.dumps(ocr_results, ensure_ascii=False, indent=2), "utf-8")

    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    meta.update({
        "ocr_count": len(ocr_results),
        "mode": "ocr_only",
        "run_id": run_dir.name[-7:]
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta
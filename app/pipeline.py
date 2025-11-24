import shutil
import os, sys, json, time, uuid, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
import cv2
import numpy as np

# Import YoloONNX and run_ocr_on_crops from utils
from utils.ocr_pipeline import YoloONNX, run_ocr_on_crops

#  Directory to save inference results (images with boxes, labels, etc.)
RUNS_DIR = Path(os.getenv("RUNS_DIR", "static/runs")).resolve()
DATA_ORIGINALS = Path(os.getenv("DATA_ORIGINALS", "static")).resolve()
CROP_MODEL_PATH = "models/best.onnx" # Default to crop model path
OCR_MODEL_PATH = "models/ocr/best.onnx" # Default to OCR model path
OCR_API_KEY = "K83109457288957"

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

def scrape_crop_ocr(site: str = "lidl", conf: float = 0.75) -> dict:
    run_dir   = _new_run_dir()
    crops_dir = run_dir / "crops"

    # 1) Scrape PNG pages for the given site and prospekt
    _try_call_scraper(site, DATA_ORIGINALS)
    pages_dir = run_dir / "pages"
    crops_dir = run_dir / "crops"
    if not crops_dir.exists():
        crops_dir.mkdir(parents=True, exist_ok=True)
    copy_directory(_last_modified_directory(DATA_ORIGINALS / site), pages_dir)

    # 2) Run YOLO and save crops
    print(f"[INFO] [pipeline] Running YOLO on pages in {pages_dir}...")
    try:
        yolo = YoloONNX(CROP_MODEL_PATH, conf_thres=conf)
        items = []
        for i, page_path in enumerate(sorted(pages_dir.glob("*.jpg")), 1):
            img = cv2.imread(str(page_path))
            if img is None: continue
            
            boxes, confidences, class_ids = yolo.predict(img)
            
            for j, (box, score, cls) in enumerate(zip(boxes, confidences, class_ids), 1):
                x1, y1, x2, y2 = map(int, box)
                crop = img[y1:y2, x1:x2]
                if crop.size == 0: continue
                
                name = f"p{i:02d}_b{j:03d}.jpg"
                outp = crops_dir / name
                cv2.imwrite(str(outp), crop)
                
                items.append({
                    "page": i,
                    "file": f"/static/runs/{run_dir.name}/crops/{name}",
                    "class_id": int(cls),
                    "score": float(score),
                    "box": [x1, y1, x2, y2]
                })
                
        meta = {"run_id": run_dir.name, "site": site, "count": len(items), "items": items}
        meta_path = run_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    except Exception as e:
        print(f"[ERROR] [pipeline] YOLO inference failed: {e}")
        return {"error": str(e)}

    
    # 3) Run OCR pipeline on the generated crops
    ocr_csv = run_dir / "ocr_results.csv"
    
    if crops_dir.exists() and list(crops_dir.glob("*.jpg")):
        print(f"[INFO] [pipeline] Running OCR on crops in {crops_dir}...")
        try:
            ocr_results = run_ocr_on_crops(
                crops_dir=crops_dir,
                output_csv=ocr_csv,
                model_path=OCR_MODEL_PATH,
                conf_threshold=conf,
                img_size=640,
                lang="de"
            )
            # Update meta.json with OCR info
            if meta_path.exists():
                meta_data = json.loads(meta_path.read_text("utf-8"))
                meta_data["ocr_count"] = len(ocr_results)
                meta_data["ocr_csv"] = f"/static/runs/{run_dir.name}/ocr_results.csv"
                meta_path.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), "utf-8")
            print(f"[INFO] [pipeline] OCR completed. {len(ocr_results)} products processed.")
        except Exception as e:
            print(f"[ERROR] [pipeline] OCR failed: {e}")

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
    Run cropping only on the latest run, without scraping new pages.
    Saves updated meta.json with count/items/ocr.
    """
    latest_run = _last_modified_directory(RUNS_DIR)
    run_dir = _last_modified_directory(latest_run)

    # Run YOLO and save crops
    print(f"[INFO] [pipeline] Running YOLO on pages in '{run_dir}':")
    try:
        yolo = YoloONNX(CROP_MODEL_PATH, conf_thres=conf)
        items = []
        
        for i, page_path in enumerate(sorted(run_dir.glob("*.jpg")), 1):
            img = cv2.imread(str(page_path))
            if img is None: continue
            print(f"[INFO] [pipeline]  Found page: {page_path.name} ({img.shape[1]}x{img.shape[0]})")
            
            boxes, confidences, class_ids = yolo.predict(img)
            
            for j, (box, score, cls) in enumerate(zip(boxes, confidences, class_ids), 1):
                x1, y1, x2, y2 = map(int, box)
                
                # Check for empty/invalid boxes
                if x2 <= x1 or y2 <= y1:
                    print(f"[WARN] Skip empty crop: {x1},{y1},{x2},{y2}")
                    continue
                    
                crop = img[y1:y2, x1:x2]
                if crop.size == 0:
                    print(f"[WARN] Skip zero-size crop: {x1},{y1},{x2},{y2}")
                    continue
                    
                name = f"p{i:02d}_b{j:03d}.jpg"
                if not (latest_run / "crops").exists():
                    (latest_run / "crops").mkdir(parents=True, exist_ok=True)
                outp = latest_run / "crops" / name
                cv2.imwrite(str(outp), crop)
                
                items.append({
                    "page": i,
                    "file": f"/static/runs/{latest_run.name}/crops/{name}",
                    "class_id": int(cls),
                    "score": float(score),
                    "box": [x1, y1, x2, y2]
                })

        # Update meta
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
        
    except Exception as e:
        print(f"[ERROR] [pipeline] Crop only failed: {e}")
        return {"error": str(e)}

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
    ocr_csv = run_dir / "ocr_results.csv"
    print(f"[INFO] [pipeline] Running OCR on crops in '{crops_dir}':")
    
    try:
        ocr_results = run_ocr_on_crops(
            crops_dir=crops_dir,
            output_csv=ocr_csv,
            model_path=OCR_MODEL_PATH,
            conf_threshold=0.25, # Default conf
            img_size=640,
            lang="de"
        )
        
        # Write results to ocr.json for backward compatibility if needed, 
        # but run_ocr_on_crops already writes to CSV.
        # Let's write to ocr.json as well since the frontend might expect it.
        ocr_json = run_dir / "ocr.json"
        ocr_json_data = []
        for res in ocr_results:
            ocr_json_data.append({
                "filename": f"{res['filename']}.jpg", # run_ocr_on_crops returns filename without ext? No, it returns stem.
                "ocr_result": {
                    "name": res["name"],
                    "price": res["price"]
                }
            })
        ocr_json.write_text(json.dumps(ocr_json_data, ensure_ascii=False, indent=2), "utf-8")

        meta_path = run_dir / "meta.json"
        meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
        meta.update({
            "ocr_count": len(ocr_results),
            "mode": "ocr_only",
            "run_id": run_dir.name[-7:]
        })
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
        return meta
        
    except Exception as e:
        print(f"[ERROR] [pipeline] OCR failed: {e}")
        return {"error": str(e)}
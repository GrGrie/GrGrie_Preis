import os
import json, shutil, time, uuid, subprocess
from pathlib import Path
from PIL import Image
from app.yolo_service import YoloService

#  Directory to save inference results (images with boxes, labels, etc.)
RUNS_DIR = Path(os.getenv("RUNS_DIR", "static/runs")).resolve()
# Do not change this file directly, use environment variables instead.
DATA_ORIGINALS = Path(os.getenv("DATA_ORIGINALS", "data/originals")).resolve()

def _new_run_dir() -> Path:
    run_id = time.strftime("%Y-%m-%d_%H-%M-%S_") + uuid.uuid4().hex[:6]
    rd = RUNS_DIR / run_id
    (rd / "pages").mkdir(parents=True, exist_ok=True)
    (rd / "crops").mkdir(parents=True, exist_ok=True)
    return rd

def _latest_dir(root: Path) -> Path:
    dirs = [p for p in root.iterdir() if p.is_dir()]
    if not dirs:
        raise RuntimeError(f"No subfolders in {root}")
    return max(dirs, key=lambda p: p.stat().st_mtime)

def _copy_pngs(src_dir: Path, dst_dir: Path) -> list[Path]:
    pages = []
    for p in sorted(src_dir.glob("*.png")):
        out = dst_dir / p.name
        shutil.copy2(p, out)
        pages.append(out)
    if not pages:
        raise RuntimeError(f"No PNG pages found in {src_dir}")
    return pages

def _try_call_scraper(site: str, out_dir: Path) -> bool:
    cmd = ["python", "scrape.py", "--site", site, "--num_prospekt", "1", "--download-path", str(out_dir)]
    try:
        subprocess.run(cmd, check=True)
        return True
    except Exception:
        return False

def run_once(site: str = "lidl", conf: float = 0.25) -> dict:
    run_dir   = _new_run_dir()
    pages_dir = run_dir / "pages"
    crops_dir = run_dir / "crops"

    # 1) Get scraper PNGs
    if not _try_call_scraper(site, pages_dir):
        # Fallback: just copy the latest folder from data/originals
        latest = _latest_dir(DATA_ORIGINALS)
        _copy_pngs(latest, pages_dir)

    # 2) Run YOLO and save crops
    yolo = YoloService(conf=conf)
    items = []
    for i, page_path in enumerate(sorted(pages_dir.glob("*.png")), 1):
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

    meta = {"run_id": run_dir.name, "site": site, "count": len(items), "items": items}
    (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return meta

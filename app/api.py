# To run: `uvicorn app.api:app --host 0.0.0.0 --port 80000 --reload`
from app.pipeline import run_once
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.ocr import ocr_folder
import json

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
RUNS_DIR = BASE_DIR / "static" / "runs"
app = FastAPI()

# static + templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# list recent runs (sorted by mtime desc)
def _recent_runs(n: int = 12):
    runs_dir = BASE_DIR / "static" / "runs"
    if not runs_dir.exists():
        return []
    items = []
    for d in runs_dir.iterdir():
        if d.is_dir() and (d / "meta.json").exists():
            items.append((d.name, d.stat().st_mtime))
    items.sort(key=lambda t: t[1], reverse=True)
    return [i[0] for i in items[:n]]

def _latest_run_dir() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    run_dirs = [p for p in RUNS_DIR.iterdir() if p.is_dir()]
    if not run_dirs:
        return None
    # newest by modification time
    return max(run_dirs, key=lambda p: p.stat().st_mtime)

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "runs": _recent_runs()})

@app.post("/run-sync")
def run_sync(site: str = Form("lidl"), num_prospekt: int = Form(1), conf: float = Form(0.25)):
    meta = run_once(site, conf, num_prospekt)
    return RedirectResponse(url=f"/done/{meta['run_id']}", status_code=303)

# lightweight done page that auto-redirects back to "/"
@app.get("/done/{run_id}")
def done(request: Request, run_id: str):
    meta_path = BASE_DIR / "static" / "runs" / run_id / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {"run_id": run_id}
    return templates.TemplateResponse("done.html", {"request": request, "meta": meta})

# raw meta.json for quick inspection
@app.get("/runs/{run_id}/meta")
def run_meta(run_id: str):
    meta_path = BASE_DIR / "static" / "runs" / run_id / "meta.json"
    if not meta_path.exists():
        return JSONResponse({"error": "meta.json not found"}, status_code=404)
    return JSONResponse(json.loads(meta_path.read_text("utf-8")))

@app.post("/runs/{run_id}/ocr")
def rerun_ocr(run_id: str):
    run_dir = BASE_DIR / "static" / "runs" / run_id
    crops   = run_dir / "crops"
    if not crops.exists():
        return JSONResponse({"error": "crops not found for this run"}, status_code=404)
    out_json = run_dir / "ocr.json"
    out_csv  = run_dir / "ocr.csv"
    info = ocr_folder(crops, out_json, out_csv)
    # patch meta.json if present
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text("utf-8"))
        meta["ocr"] = info
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return JSONResponse(info)

@app.post("/run-ocr-latest")
def run_ocr_latest():
    run_dir = _latest_run_dir()
    if run_dir is None:
        return JSONResponse({"error": "No runs found"}, status_code=404)

    crops = run_dir / "crops"
    if not crops.exists():
        return JSONResponse({"error": f"No crops found in {run_dir.name}"}, status_code=404)

    out_json = run_dir / "ocr.json"
    out_csv  = run_dir / "ocr.csv"
    print(f"[DEBUG] Running OCR on latest run: {run_dir.name}")
    info = ocr_folder(crops, out_json, out_csv)

    # Patch meta.json if present
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        meta["ocr"] = info
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Redirect to the existing "done" page for this run (so the user sees results)
    return RedirectResponse(url=f"/done/{run_dir.name}", status_code=303)

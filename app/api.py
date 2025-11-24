# To run: `uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload`
# docker build -t grgrie-inference .
# docker run -p 8000:8000 -v $(pwd)/data:/app/data grgrie-inference

from app.pipeline import crop_only, scrape_only, ocr_latest_run, scrape_crop_ocr
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
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

# Button "Scrape + Crop + OCR"
@app.post("/scrape-crop-ocr")
def run_sync(site: str = Form("lidl"), conf: float = Form(0.75)):
    """
    Run the full pipeline (scrape + crop + ocr) for the given site and confidence threshold.
    """
    print(f"[INFO] [api] Starting full run for site '{site}' with conf={conf}...")
    meta = scrape_crop_ocr(site, conf)
    return RedirectResponse(url=f"/done/{meta['run_id']}", status_code=303)

@app.post("/scrape")
def scrape_only_endpoint(site: str = Form(...)):
    """
    Scrape pages for the given site and prospekt count, without running inference.
    """
    meta = scrape_only(site=site)
    return RedirectResponse(url=f"/done/{meta['run_id']}", status_code=303)

@app.post("/crop")
def crop_latest(site: str = Form("lidl"), conf: float = Form(0.25)):
    """
    Run cropping only on the latest run, without scraping new pages.
    """
    meta = crop_only(site=site, conf=conf)
    return RedirectResponse(url=f"/done/{meta['run_id']}", status_code=303)

@app.post("/ocr-latest")
def ocr_latest_run_endpoint():
    """
    Run OCR only on the latest run, without scraping or cropping.
    """
    meta = ocr_latest_run()
    return RedirectResponse(url=f"/done/{meta['run_id']}", status_code=303)

# lightweight done page that auto-redirects back to "/"
@app.get("/done/{run_id}")
def done(request: Request, run_id: str):
    meta_path = BASE_DIR / "static" / "runs" / run_id / "meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {"run_id": run_id}
    return templates.TemplateResponse("done.html", {"request": request, "meta": meta})

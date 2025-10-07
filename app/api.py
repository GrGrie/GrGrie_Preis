from app.pipeline import run_once
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
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

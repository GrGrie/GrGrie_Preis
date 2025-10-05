from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import ensure_dirs, RUNS_DIR
from app.pipeline import run_once
from app.yolo_service import YoloService
import json

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="Booklet API", version="0.2.0")
ensure_dirs()

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

yolo = YoloService()

@app.get("/health")
def health(): return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    runs = sorted([p for p in RUNS_DIR.iterdir() if (p / "meta.json").exists()], reverse=True)[:20]
    return templates.TemplateResponse("index.html", {"request": request, "runs": [p.name for p in runs]})

@app.post("/run")
def start_run(background_tasks: BackgroundTasks, site: str = Form("lidl"), conf: float = Form(0.25)):
    background_tasks.add_task(run_once, site, conf)
    return RedirectResponse("/", status_code=303)

@app.get("/runs/{run_id}", response_class=HTMLResponse)
def view_run(request: Request, run_id: str):
    meta = json.loads((RUNS_DIR / run_id / "meta.json").read_text("utf-8"))
    return templates.TemplateResponse("run.html", {"request": request, "meta": meta})

@app.post("/predict")
async def predict(file: UploadFile = File(...), conf: float = Form(0.25)):
    data = await file.read()
    dets = yolo.predict_image_bytes(data, conf)
    return JSONResponse({"detections": dets})

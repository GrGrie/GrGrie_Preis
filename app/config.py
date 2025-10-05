import os
from pathlib import Path

# Do not change this file directly, use environment variables instead.
DATA_ORIGINALS = Path(os.getenv("DATA_ORIGINALS", "data/originals")).resolve()

#  Directory to save inference results (images with boxes, labels, etc.)
RUNS_DIR = Path(os.getenv("RUNS_DIR", "static/runs")).resolve()

def ensure_dirs():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
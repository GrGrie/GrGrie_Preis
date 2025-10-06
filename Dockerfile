FROM python:3.11-slim AS runtime

# 2.1 Custom flags
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 2.2 System libs for onnxruntime / pillow / opencv-headless
# RUN apt-get update && apt-get install -y --no-install-recommends \
#      ca-certificates libgomp1 libglib2.0-0 \
#    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2.3 Install only runtime dependencies
RUN pip install --no-cache-dir \
      onnxruntime \
      fastapi uvicorn \
      numpy pillow \
      opencv-python-headless

# 2.4 Copying code
COPY app/ app/
COPY yolo_predict.py yolo_predict.py
COPY utils/ utils/
COPY scrape.py scrape.py  

# 2.5 Copy only ONNX model
COPY models/best.onnx /models/best.onnx

# 2.6 Environment variables
ENV MODEL_PATH=/models/best.onnx \
    PORT=8000

EXPOSE 8000

# 2.7 Starting without Poetry
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]

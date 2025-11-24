# Use Python 3.13 slim image for minimal size
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=/app/models/best.onnx

# Install system dependencies required for OpenCV and PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We use --no-cache-dir to keep the image small
# We install CPU-only PyTorch explicitly to avoid downloading CUDA libs
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    onnxruntime \
    ultralytics \
    paddlepaddle==2.6.2 \
    paddleocr==2.9.1 \
    fastapi \
    uvicorn \
    python-multipart \
    jinja2 \
    opencv-python-headless \
    pillow \
    numpy<2.0 \
    python-telegram-bot \
    python-dotenv \
    requests

# Copy application code
COPY app /app/app
COPY templates /app/templates
COPY static /app/static
COPY models /app/models

# Create a directory for data if it doesn't exist (mounted volume)
RUN mkdir -p /app/data

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]

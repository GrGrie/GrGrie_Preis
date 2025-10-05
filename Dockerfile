FROM python:3.13-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu


WORKDIR /app

# Install poetry and Configure poetry to not create virtual environment inside the container
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false

# Copy poetry files
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-root --only main

# Cache cleanup
RUN rm -rf /root/.cache/pip /root/.cache/pypoetry


# Copy code files
COPY app/ app/
COPY models/best.pt models/best.pt
COPY yolo_predict.py yolo_predict.py
COPY utils/ utils/
COPY scrape.py scrape.py

ENV PORT=8000 \
    MODEL_PATH=models/best.pt \
    TORCH_DEVICE=auto \
    CONF_THRESHOLD=0.25

EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]


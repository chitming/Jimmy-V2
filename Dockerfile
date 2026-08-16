# TDR — Technical Drawing Reader
# Multi-stage: Vite UI build → Python API serving UI + OCR/DXF stack

# ---- Frontend build ----
FROM node:22-bookworm-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Runtime ----
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        git \
        curl \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libxcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching
COPY backend/requirements.txt backend/requirements-windows-core.txt ./
RUN python -m pip install --upgrade pip wheel setuptools \
    && (pip install -r requirements.txt \
        || (echo "Full stack install failed; using core deps" \
            && pip install -r requirements-windows-core.txt))

# Application code + prebuilt UI (served by FastAPI from app/static)
COPY backend/ ./
COPY --from=frontend /src/dist ./app/static

# Persist uploads, library crops, SQLite DB, pipeline outputs
RUN mkdir -p /app/data/uploads /app/data/pages /app/data/crops \
        /app/data/library/Info\ Block /app/data/library/Drawing \
        /app/data/pipeline /app/data/exports /app/data/models \
    && useradd --create-home --uid 10001 tdr \
    && chown -R tdr:tdr /app
USER tdr

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD curl -sf http://127.0.0.1:8000/api/stats >/dev/null || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

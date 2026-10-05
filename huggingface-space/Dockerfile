# ============================================================================
# DocuTrust — single-container build for Hugging Face Spaces (Docker SDK)
# Place this file at the ROOT of your repo (same level as backend/ and frontend/)
# ============================================================================

# ---- Stage 1: build the React frontend --------------------------------------
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- Stage 2: final image — backend + nginx + supervisor --------------------
FROM python:3.11-slim

WORKDIR /app

# System deps: build tools for Python packages, nginx to serve+proxy, supervisor to run both
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    curl \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

# CPU-only PyTorch first (same as your original backend/Dockerfile)
RUN pip install --no-cache-dir \
    torch==2.3.0 \
    --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt

COPY backend/app/ ./app/

# Built frontend static files
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# nginx + supervisor config (see the other two files in this folder)
COPY huggingface-space/nginx-space.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default
COPY huggingface-space/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# HF Spaces expects the container to listen on 7860 by default
EXPOSE 7860

# Writable dirs the app needs (HF Spaces runs containers as a non-root UID by default)
RUN mkdir -p /tmp/docutrust_uploads /root/.cache/huggingface \
    && chmod -R 777 /tmp/docutrust_uploads /root/.cache/huggingface /var/log/nginx /var/lib/nginx

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

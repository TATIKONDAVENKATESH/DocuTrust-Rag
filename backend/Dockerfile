FROM python:3.11-slim

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Upgrade pip ───────────────────────────────────────────────────────────────
RUN pip install --no-cache-dir --upgrade pip

# ── Install CPU-only PyTorch FIRST ───────────────────────────────────────────
# This must happen before requirements.txt so sentence-transformers sees the
# already-satisfied torch and does NOT pull the CUDA wheel.
RUN pip install --no-cache-dir \
    torch==2.3.0 \
    --index-url https://download.pytorch.org/whl/cpu

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy only requirements first so Docker cache is not busted by source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application source ───────────────────────────────────────────────────
COPY app/ ./app/

EXPOSE 8000

# HuggingFace model cache is mounted as a volume — models download once and
# persist across container restarts (see docker-compose.yml hf_cache volume).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
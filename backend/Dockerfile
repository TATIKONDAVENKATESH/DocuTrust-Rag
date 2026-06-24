FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install CPU-only PyTorch first to prevent pip pulling CUDA build via sentence-transformers
RUN pip install --no-cache-dir \
    torch==2.3.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Install project dependencies (torch is already satisfied above, so sentence-transformers
# won't try to upgrade it to a CUDA version)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

EXPOSE 8000

# Models are downloaded on first request and cached in HuggingFace cache directory.
# Mount a volume at /root/.cache/huggingface to persist across container restarts.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
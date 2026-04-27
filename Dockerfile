FROM python:3.10-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Step 1: Pin numpy + scipy BEFORE torch so torch never gets a chance to pull in numpy 2.x.
# Torch only requires numpy>=1.16.5 — it will not upgrade a pre-installed numpy 1.26.4.
RUN pip install --no-cache-dir "numpy==1.26.4" "scipy==1.13.1"

# Step 2: Install CPU-only PyTorch — numpy 1.26.4 is already present, pip skips it.
RUN pip install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Step 3: Install the rest (numpy + scipy already locked, pip won't touch them).
RUN pip install --no-cache-dir -r requirements.txt

# Step 4: Pre-download EasyOCR models at BUILD time so the container is ready instantly.
# Models are baked into the image — no CDN call needed at runtime.
RUN python3 -c "import easyocr; easyocr.Reader(['ta', 'en'], gpu=False, model_storage_directory='/app/models', download_enabled=True)"

# Bump this to force Railway to invalidate only the app-code layer (not torch/models).
ARG CACHE_BUST=8

# Copy app
COPY . .

# Fix path
RUN mkdir -p static/uploads

EXPOSE 8000

CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
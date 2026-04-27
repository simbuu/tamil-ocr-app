FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# ✅ Install CPU-only PyTorch FIRST
RUN pip install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# ✅ Force numpy 1.x + scipy 1.13.1 AFTER torch (torch upgrades numpy to 2.x otherwise)
# The torch numpy-bridge warning is non-fatal — torch CPU inference still works fine
RUN pip install --no-cache-dir --force-reinstall "numpy==1.26.4" "scipy==1.13.1"

# ✅ Then install rest (make sure torch is NOT in requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Fix path
RUN mkdir -p static/uploads

EXPOSE 8000

CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
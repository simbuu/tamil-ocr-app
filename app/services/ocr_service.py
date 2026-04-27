"""
OCR Service — v2
Now instrumented with per-stage timing for performance analysis.
"""

import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
import io
import re
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# easyocr is intentionally NOT imported at module level.
# Importing it at startup triggers torch + scipy C extensions immediately,
# which causes "cannot load module more than once per process" when uvloop
# initialises alongside them. Deferred import fixes this.
_reader = None


def get_reader():
    """Lazy-load the EasyOCR reader with Tamil + English."""
    import easyocr  # deferred — keeps uvicorn startup clean
    global _reader
    if _reader is None:
        logger.info("Loading EasyOCR model for Tamil + English…")
        _reader = easyocr.Reader(
            ["ta", "en"],
            gpu=False,
            model_storage_directory="/app/models",  # absolute path — matches Dockerfile pre-download
            download_enabled=False,                 # models are baked into the image at build time
        )
        logger.info("EasyOCR model loaded ✅")
    return _reader


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Return (width, height) of image."""
    img = Image.open(io.BytesIO(image_bytes))
    return img.size


# ── Image Preprocessing ───────────────────────────────────────────────────────

def preprocess_image(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    min_dim = 1200
    w, h = img.size
    if max(w, h) < min_dim:
        scale = min_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    gray = img.convert("L")
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    gray = ImageEnhance.Sharpness(gray).enhance(2.5)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))

    arr = np.array(gray, dtype=np.uint8)
    threshold = int(arr.mean() * 0.85)
    binary = np.where(arr > threshold, 255, 0).astype(np.uint8)
    return binary


# ── OCR row parsing (unchanged) ───────────────────────────────────────────────

FLOWER_KEYWORDS_EN = [
    "rose", "jasmine", "marigold", "lotus", "lily",
    "chrysanthemum", "tuberose", "crossandra", "kanakambaram",
]

FLOWER_KEYWORDS_TA = [
    "ரோஜா", "மல்லிகை", "செம்பருத்தி", "தாமரை", "லில்லி",
    "சேவந்தி", "நிலாம்பரி", "குறிஞ்சி", "கனகாம்பரம்",
]


def extract_transactions_from_ocr(ocr_results: list[dict]) -> list[dict]:
    if not ocr_results:
        return []

    sorted_results = sorted(ocr_results, key=lambda r: (r["bbox"][0][1], r["bbox"][0][0]))

    rows = []
    current_row = []
    prev_y = None
    ROW_THRESHOLD = 30

    for item in sorted_results:
        y = item["bbox"][0][1]
        if prev_y is None or abs(y - prev_y) <= ROW_THRESHOLD:
            current_row.append(item)
        else:
            if current_row:
                rows.append(current_row)
            current_row = [item]
        prev_y = y

    if current_row:
        rows.append(current_row)

    transactions = []
    for row in rows:
        row_texts = [r["text"].strip() for r in row if r["text"].strip()]
        row_text = " ".join(row_texts)
        avg_conf = sum(r["confidence"] for r in row) / len(row)

        parsed = _parse_row(row_text, avg_conf)
        if parsed:
            transactions.append(parsed)

    return transactions


def _parse_row(text: str, confidence: float) -> Optional[dict]:
    # Match weight with optional unit — supports kg, g/gm/grams and Tamil equivalents
    weight_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|kgs?|கி\.?கி\.?|கிலோ|grams?|gm|g|கிராம்)?",
        re.IGNORECASE,
    )
    weight_matches = weight_pattern.findall(text)
    if not weight_matches:
        return None

    raw_value, unit = weight_matches[-1]
    raw_value = float(raw_value)
    unit = (unit or "").lower().strip(".")

    # Convert grams → kg
    if unit in ("g", "gm", "gram", "grams", "கிராம்"):
        weight_kg = raw_value / 1000
    else:
        weight_kg = raw_value  # already kg (or unitless — assume kg)

    if weight_kg <= 0 or weight_kg > 5000:
        return None

    flower_type_en = None
    flower_type_ta = None
    text_lower = text.lower()
    for flower in FLOWER_KEYWORDS_EN:
        if flower in text_lower:
            flower_type_en = flower.title()
            break
    for flower in FLOWER_KEYWORDS_TA:
        if flower in text:
            flower_type_ta = flower
            break
    flower_type = flower_type_en or flower_type_ta or "Unknown"

    clean = re.sub(weight_pattern, "", text)
    for f in FLOWER_KEYWORDS_EN + FLOWER_KEYWORDS_TA:
        clean = clean.replace(f, "").replace(f.lower(), "")
    clean = re.sub(r"[^\w\s\u0B80-\u0BFF]", " ", clean).strip()
    clean = re.sub(r"\s+", " ", clean)

    tamil_chars = re.findall(r"[\u0B80-\u0BFF]+", clean)
    latin_chars = re.findall(r"[A-Za-z]+", clean)

    customer_name_ta = " ".join(tamil_chars) if tamil_chars else None
    customer_name_en = " ".join(latin_chars) if latin_chars else None
    customer_name = customer_name_en or customer_name_ta or "Unknown"

    return {
        "customer_name": customer_name,
        "customer_name_tamil": customer_name_ta,
        "flower_type": flower_type,
        "flower_type_tamil": flower_type_ta,
        "weight_kg": weight_kg,
        "ocr_confidence": round(confidence, 3),
        "raw_text": text,
    }


# ── Main entry — now with timing instrumentation ──────────────────────────────

def run_ocr(image_bytes: bytes) -> dict:
    """
    Full pipeline with per-stage timing.
    Returns timing data so it can be persisted to ocr_sessions table.
    """
    timings = {"preprocessing_ms": 0, "ocr_ms": 0, "parsing_ms": 0}
    try:
        # Image dimensions
        img_w, img_h = get_image_dimensions(image_bytes)

        # 1. Preprocess
        t0 = time.perf_counter()
        processed = preprocess_image(image_bytes)
        timings["preprocessing_ms"] = int((time.perf_counter() - t0) * 1000)

        # 2. OCR
        t0 = time.perf_counter()
        reader = get_reader()
        raw = reader.readtext(processed, detail=1, paragraph=False)
        timings["ocr_ms"] = int((time.perf_counter() - t0) * 1000)

        normalized = [
            {"bbox": [[float(x), float(y)] for x, y in item[0]],
             "text": item[1], "confidence": float(item[2])}
            for item in raw
        ]

        # 3. Parse
        t0 = time.perf_counter()
        transactions = extract_transactions_from_ocr(normalized)
        timings["parsing_ms"] = int((time.perf_counter() - t0) * 1000)

        # Aggregate confidence
        avg_conf = (sum(n["confidence"] for n in normalized) / len(normalized)) if normalized else None

        return {
            "success": True,
            "raw_results": normalized,
            "transactions": transactions,
            "word_count": len(normalized),
            "transaction_count": len(transactions),
            "avg_confidence": round(avg_conf, 3) if avg_conf else None,
            "image_width": img_w,
            "image_height": img_h,
            "timings": timings,
        }

    except Exception as e:
        logger.error(f"OCR pipeline error: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "transactions": [],
            "timings": timings,
        }

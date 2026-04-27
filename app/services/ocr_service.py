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
    "arali", "oleander", "nandiyar", "champak",
    "mullai", "samandhi", "sevanthi", "thulasi",
]

FLOWER_KEYWORDS_TA = [
    # Common market flowers
    "ரோஜா",          # rose
    "மல்லிகை",        # jasmine
    "செம்பருத்தி",    # hibiscus
    "தாமரை",          # lotus
    "லில்லி",         # lily
    "சேவந்தி",        # chrysanthemum / sevanthi
    "நிலாம்பரி",      # tuberose
    "குறிஞ்சி",       # kurinji
    "கனகாம்பரம்",    # kanakambaram / crossandra
    "அரளி",           # arali / oleander (common variant)
    "அரலி",           # arali (alternate spelling OCR often produces)
    "நந்தியம்வட்டை", # nandiyamvattai
    "நந்தியம்வன்",   # nandiyamvan
    "நந்தியார்வட்டை",# nandiyar
    "முல்லை",         # mullai / jasmine variety
    "சாமந்தி",        # samandhi / chrysanthemum
    "துளசி",          # thulasi / tulsi
    "பாரிஜாதம்",     # parijatham / night jasmine
    "மரிகோல்டு",     # marigold (transliterated)
]


def extract_transactions_from_ocr(ocr_results: list[dict]) -> list[dict]:
    if not ocr_results:
        return []

    sorted_results = sorted(ocr_results, key=lambda r: (r["bbox"][0][1], r["bbox"][0][0]))

    # Group OCR words into rows by Y-position.
    # ROW_THRESHOLD: pixels of vertical tolerance — increased for A4 template rows.
    # We use the *centre* Y of each bounding box for stability.
    rows = []
    current_row = []
    prev_y = None
    ROW_THRESHOLD = 20   # tight — template rows are ~40px apart at 150dpi

    for item in sorted_results:
        # Use centre Y of bbox for more stable grouping
        ys = [pt[1] for pt in item["bbox"]]
        y = sum(ys) / len(ys)
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
        # Sort words in row left-to-right before joining
        row_sorted = sorted(row, key=lambda r: r["bbox"][0][0])
        row_texts = [r["text"].strip() for r in row_sorted if r["text"].strip()]
        row_text = " ".join(row_texts)
        avg_conf = sum(r["confidence"] for r in row_sorted) / len(row_sorted)

        parsed = _parse_row(row_text, avg_conf)
        if parsed:
            # ── KEY FILTER: discard empty template rows ────────────────────
            # Empty rows only have the printed S.No number; OCR sees just
            # a digit and the parser treats it as a weight. Reject any row
            # where BOTH customer and flower are unknown — it's a blank row.
            if parsed["customer_name"] == "Unknown" and parsed["flower_type"] == "Unknown":
                continue
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

    # ── Grade detection: standalone A / B / C in row ─────────────────────────
    grade_match = re.search(r"\b([ABC])\b", text, re.IGNORECASE)
    grade = grade_match.group(1).upper() if grade_match else None

    tamil_words = re.findall(r"[\u0B80-\u0BFF]+", clean)
    # Require ≥2 Tamil characters per word to filter out stray glyphs from S.No / table borders
    tamil_words = [w for w in tamil_words if len(w) >= 2]

    # Strip grade letters and unit words that bleed into customer name
    latin_words = [w for w in re.findall(r"[A-Za-z]+", clean)
                   if w.upper() not in ("A", "B", "C", "KG", "KGS", "GM", "G", "GRAM", "GRAMS")
                   and len(w) >= 2]

    customer_name_ta = " ".join(tamil_words) if tamil_words else None
    customer_name_en = " ".join(latin_words) if latin_words else None
    customer_name = customer_name_en or customer_name_ta or "Unknown"

    return {
        "customer_name": customer_name,
        "customer_name_tamil": customer_name_ta,
        "flower_type": flower_type,
        "flower_type_tamil": flower_type_ta,
        "weight_kg": round(weight_kg, 4),
        "grade": grade,
        "ocr_confidence": round(confidence, 3),
        "raw_text": text,
    }


# ── Main entry — now with timing instrumentation ──────────────────────────────

def run_ocr(image_bytes: bytes) -> dict:
    """
    Full pipeline with per-stage timing.
    Returns timing 
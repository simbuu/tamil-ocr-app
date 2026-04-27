"""
OCR Service - v2
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

_reader = None


def get_reader():
    """Lazy-load the EasyOCR reader with Tamil + English."""
    import easyocr
    global _reader
    if _reader is None:
        logger.info("Loading EasyOCR model for Tamil + English...")
        _reader = easyocr.Reader(
            ["ta", "en"],
            gpu=False,
            model_storage_directory="/app/models",
            download_enabled=False,
        )
        logger.info("EasyOCR model loaded")
    return _reader


def get_image_dimensions(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes))
    return img.size


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    min_dim = 1200
    max_dim = 1800  # cap: larger images don't improve OCR but cost a lot of CPU time
    longest = max(w, h)
    if longest < min_dim:
        scale = min_dim / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    elif longest > max_dim:
        scale = max_dim / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    w, h = img.size
    gray = img.convert("L")
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    gray = ImageEnhance.Sharpness(gray).enhance(2.5)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    arr = np.array(gray, dtype=np.uint8)
    threshold = int(arr.mean() * 0.85)
    binary = np.where(arr > threshold, 255, 0).astype(np.uint8)
    return binary


# Numbered flower codes — must match report_service.FLOWER_CODE_LEGEND
FLOWER_CODE_MAP = {
    "1":  "Jasmine",        # மல்லிகை
    "2":  "Rose",           # ரோஜா
    "3":  "Chrysanthemum",  # சேவந்தி
    "4":  "Crossandra",     # கனகாம்பரம்
    "5":  "Oleander",       # அரளி
    "6":  "Mullai",         # முல்லை
    "7":  "Lotus",          # தாமரை
    "8":  "Marigold",       # மரிகோல்டு
    "9":  "Sevanthi",       # சாமந்தி
    "10": "Tuberose",       # நிலாம்பரி
}

FLOWER_KEYWORDS_EN = [
    "rose", "jasmine", "marigold", "lotus", "lily",
    "chrysanthemum", "tuberose", "crossandra", "kanakambaram",
    "arali", "oleander", "nandiyar", "champak",
    "mullai", "samandhi", "sevanthi", "thulasi",
]

FLOWER_KEYWORDS_TA = [
    "ரோஜா",
    "மல்லிகை",
    "செம்பருத்தி",
    "தாமரை",
    "லில்லி",
    "சேவந்தி",
    "நிலாம்பரி",
    "குறிஞ்சி",
    "கனகாம்பரம்",
    "அரளி",
    "அரலி",
    "நந்தியம்வட்டை",
    "நந்தியம்வன்",
    "நந்தியார்வட்டை",
    "முல்லை",
    "சாமந்தி",
    "துளசி",
    "பாரிஜாதம்",
    "மரிகோல்டு",
]


def _bbox_center(bbox):
    """Return (cx, cy) centre of a bounding box."""
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _assign_column(cx: float, img_w: float) -> str:
    """
    Map a word's horizontal centre to a template column.
    Calibrated from observed OCR output — weight values land at ~83% x,
    so weight extends to 90% and grade takes the last 10%.
      S.No        : 0  – 10 %
      CustomerName: 10 – 40 %
      FlowerType  : 40 – 65 %
      Weight      : 65 – 90 %
      Grade       : 90 – 100 %
    """
    ratio = cx / img_w if img_w else 0
    if ratio < 0.10:
        return "sno"
    if ratio < 0.40:
        return "name"
    if ratio < 0.65:
        return "flower"
    if ratio < 0.90:
        return "weight"
    return "grade"


def extract_transactions_from_ocr(ocr_results: list) -> list:
    if not ocr_results:
        logger.warning("OCR_PARSE: no raw results from EasyOCR — image may be blank or unreadable")
        return []

    logger.info("OCR_PARSE: %d raw OCR items received", len(ocr_results))

    # Estimate image bounds from all bounding boxes
    all_xs = [pt[0] for item in ocr_results for pt in item["bbox"]]
    all_ys = [pt[1] for item in ocr_results for pt in item["bbox"]]
    img_w = max(all_xs) if all_xs else 1
    img_h = max(all_ys) if all_ys else 1
    logger.info("OCR_PARSE: estimated image bounds w=%.0f h=%.0f", img_w, img_h)

    # Skip the top 18 % (shop name, date, column labels)
    # and the bottom 12 % (grade legend footer).
    header_cutoff = img_h * 0.18
    footer_cutoff = img_h * 0.88
    logger.info("OCR_PARSE: header cutoff y=%.0f (18%%), footer cutoff y=%.0f (88%%) of %.0f",
                header_cutoff, footer_cutoff, img_h)

    data_items = []
    for item in ocr_results:
        _, cy = _bbox_center(item["bbox"])
        if cy <= header_cutoff:
            logger.debug("OCR_PARSE: HEADER_SKIP y=%.0f text=%r", cy, item["text"])
            continue
        if cy >= footer_cutoff:
            logger.debug("OCR_PARSE: FOOTER_SKIP y=%.0f text=%r", cy, item["text"])
            continue
        data_items.append(item)

    logger.info("OCR_PARSE: %d items remain after header skip (removed %d)",
                len(data_items), len(ocr_results) - len(data_items))

    if not data_items:
        logger.warning("OCR_PARSE: all items were in header zone — header_cutoff may be too large")
        return []

    # Log all surviving items for full visibility
    for item in sorted(data_items, key=lambda r: _bbox_center(r["bbox"])[1]):
        cx, cy = _bbox_center(item["bbox"])
        col = _assign_column(cx, img_w)
        logger.info("OCR_PARSE: item  y=%.0f x=%.0f (%.1f%%) → col=%-6s  conf=%.2f  text=%r",
                    cy, cx, 100 * cx / img_w, col, item["confidence"], item["text"])

    # Group items into horizontal rows by centre-Y proximity
    sorted_items = sorted(data_items, key=lambda r: _bbox_center(r["bbox"])[1])

    rows = []
    current_row = []
    prev_y = None
    ROW_THRESHOLD = 22

    for item in sorted_items:
        _, cy = _bbox_center(item["bbox"])
        if prev_y is None or abs(cy - prev_y) <= ROW_THRESHOLD:
            current_row.append(item)
        else:
            if current_row:
                rows.append(current_row)
            current_row = [item]
        prev_y = cy

    if current_row:
        rows.append(current_row)

    logger.info("OCR_PARSE: grouped into %d rows", len(rows))

    # For each row assign words to columns by X-position, then parse
    transactions = []
    for row_idx, row in enumerate(rows):
        cols: dict = {"sno": [], "name": [], "flower": [], "weight": [], "grade": []}
        confidences = []
        for item in row:
            cx, _ = _bbox_center(item["bbox"])
            col = _assign_column(cx, img_w)
            text = item["text"].strip()
            if text:
                cols[col].append(text)
            confidences.append(item["confidence"])

        avg_conf = sum(confidences) / len(confidences)

        name_text   = " ".join(cols["name"])
        flower_text = " ".join(cols["flower"])
        weight_text = " ".join(cols["weight"])
        grade_text  = " ".join(cols["grade"])

        logger.info(
            "OCR_PARSE: row %d → name=%r  flower=%r  weight=%r  grade=%r  conf=%.2f",
            row_idx, name_text, flower_text, weight_text, grade_text, avg_conf,
        )

        parsed = _parse_columns(name_text, flower_text, weight_text, grade_text, avg_conf)
        if parsed:
            logger.info("OCR_PARSE: row %d → ACCEPTED: customer=%r flower=%r weight_kg=%.4f",
                        row_idx, parsed["customer_name"], parsed["flower_type"], parsed["weight_kg"])
            transactions.append(parsed)
        else:
            logger.info("OCR_PARSE: row %d → REJECTED (no valid weight in weight column)", row_idx)

    logger.info("OCR_PARSE: final transaction count = %d", len(transactions))
    return transactions


def _parse_columns(
    name_text: str,
    flower_text: str,
    weight_text: str,
    grade_text: str,
    confidence: float,
) -> Optional[dict]:
    """
    Parse a single data row using pre-split column text.
    Each argument contains only the OCR words that fell inside that column.
    """
    # ── Weight ────────────────────────────────────────────────────────────────
    weight_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*(kg|kgs?|grams?|gm|g)?", re.IGNORECASE
    )
    weight_matches = weight_pattern.findall(weight_text)
    weight_kg = 0.0
    if not weight_matches:
        # No number in weight column — check if row has any useful content at all.
        # If name and flower are both empty, skip. Otherwise keep with weight=0
        # so the user can fill in the weight manually.
        has_name   = bool(name_text.strip())
        has_flower = bool(flower_text.strip())
        if not has_name and not has_flower:
            logger.debug("OCR_PARSE: _parse_columns reject — no weight, no name, no flower")
            return None
        logger.debug("OCR_PARSE: _parse_columns — weight missing, keeping row for manual entry")
    else:
        raw_value, unit = weight_matches[-1]
        raw_value = float(raw_value)
        unit = (unit or "").lower().strip(".")

        if unit in ("kg", "kgs"):
            weight_kg = raw_value
        else:
            # Template column is Weight(g) — default to grams when no unit written
            weight_kg = raw_value / 1000

        if weight_kg < 0 or weight_kg > 500:
            logger.debug("OCR_PARSE: _parse_columns reject — weight_kg=%.4f out of range", weight_kg)
            return None

    # ── Grade ─────────────────────────────────────────────────────────────────
    grade_match = re.search(r"\b([ABC])\b", grade_text, re.IGNORECASE)
    # Also check weight column (sometimes written adjacent)
    if not grade_match:
        grade_match = re.search(r"\b([ABC])\b", weight_text, re.IGNORECASE)
    grade = grade_match.group(1).upper() if grade_match else None

    # ── Flower type ───────────────────────────────────────────────────────────
    # First check for a numeric flower code (1–10) — these come from the new
    # pre-printed template and are read by OCR very reliably.
    flower_code = flower_text.strip().lstrip("0")  # strip leading zeros just in case
    flower_type_ta = None
    if flower_code in FLOWER_CODE_MAP:
        flower_type = FLOWER_CODE_MAP[flower_code]
    else:
        flower_lower = flower_text.lower()
        flower_type_en = next(
            (f.title() for f in FLOWER_KEYWORDS_EN if f in flower_lower), None
        )
        flower_type_ta = next(
            (f for f in FLOWER_KEYWORDS_TA if f in flower_text), None
        )
        flower_type = flower_type_en or flower_type_ta or (flower_text.strip() or "Unknown")

    # ── Customer name ─────────────────────────────────────────────────────────
    tamil_words = [w for w in re.findall(r"[஀-௿]+", name_text) if len(w) >= 2]
    latin_words = [
        w for w in re.findall(r"[A-Za-z]+", name_text)
        if w.upper() not in ("A", "B", "C", "KG", "KGS", "GM", "G", "GRAM", "GRAMS")
        and len(w) >= 2
    ]
    customer_name_ta = " ".join(tamil_words) if tamil_words else None
    customer_name_en = " ".join(latin_words) if latin_words else None
    customer_name = customer_name_en or customer_name_ta or (name_text.strip() or "Unknown")

    raw_text = " | ".join(filter(None, [name_text, flower_text, weight_text, grade_text]))

    return {
        "customer_name": customer_name,
        "customer_name_tamil": customer_name_ta,
        "flower_type": flower_type,
        "flower_type_tamil": flower_type_ta,
        "weight_kg": round(weight_kg, 4),
        "grade": grade,
        "ocr_confidence": round(confidence, 3),
        "raw_text": raw_text,
    }


def run_ocr(image_bytes: bytes) -> dict:
    """Full OCR pipeline with per-stage timing."""
    timings = {"preprocessing_ms": 0, "ocr_ms": 0, "parsing_ms": 0}
    try:
        img_w, img_h = get_image_dimensions(image_bytes)

        t0 = time.perf_counter()
        processed = preprocess_image(image_bytes)
        timings["preprocessing_ms"] = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        reader = get_reader()
        raw = reader.readtext(processed, detail=1, paragraph=False)
        timings["ocr_ms"] = int((time.perf_counter() - t0) * 1000)

        normalized = [
            {
                "bbox": [[float(x), float(y)] for x, y in item[0]],
                "text": item[1],
                "confidence": float(item[2]),
            }
            for item in raw
        ]

        t0 = time.perf_counter()
        transactions = extract_transactions_from_ocr(normalized)
        timings["parsing_ms"] = int((time.perf_counter() - t0) * 1000)

        avg_conf = (
            sum(n["confidence"] for n in normalized) / len(normalized)
        ) if normalized else None

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
        logger.error("OCR pipeline error: %s", e, exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "transactions": [],
            "timings": timings,
        }

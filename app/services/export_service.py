"""
Export Service — Bundles images + ground-truth labels into a ZIP file.
This data can be used to fine-tune EasyOCR or to evaluate other OCR engines.
"""

import io
import json
import zipfile
import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.ocr_session import OCRSession

UPLOAD_DIR = "app/static/uploads"


def export_training_data(db: Session, only_corrected: bool = True) -> bytes:
    """
    Export a ZIP archive containing:
      /images/<session_id>.jpg     ← original images
      /labels.jsonl                ← one JSON per line per transaction
      /sessions.jsonl              ← one JSON per OCR session (with timing/raw output)
      /README.md                   ← describes the format

    If only_corrected=True, includes only transactions where users edited OCR output
    (highest-value training data).
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        # ── README ─────────────────────────────────────────────────────────
        readme = f"""# Tamil OCR Training Data Export

Generated: {datetime.utcnow().isoformat()}Z
Filter: {"corrected only" if only_corrected else "all OCR-derived transactions"}

## Files

- `images/` — original uploaded images, named by OCR session ID
- `labels.jsonl` — newline-delimited JSON, one transaction per line
- `sessions.jsonl` — newline-delimited JSON, one OCR session per line

## Label Schema (labels.jsonl)

Each line:
```json
{{
  "transaction_id": 123,
  "ocr_session_id": 45,
  "image": "images/45.jpg",
  "ocr_extracted": {{
    "customer_name": "Rajan",
    "flower_type": "Jasmine",
    "weight_kg": 5.25
  }},
  "ground_truth": {{
    "customer_name": "Rajesh",
    "flower_type": "Jasmine",
    "weight_kg": 5.25
  }},
  "corrections": [
    {{"field": "customer_name", "ocr": "Rajan", "saved": "Rajesh"}}
  ],
  "confidence": 0.62
}}
```

## How to Use

This data can be used to:
1. Fine-tune EasyOCR's recognition model on your specific handwriting style
2. Benchmark alternative OCR engines (PaddleOCR, TrOCR, Tesseract) using the ground truth
3. Identify systematic OCR errors for targeted fixes
"""
        zf.writestr("README.md", readme)

        # ── Build query ────────────────────────────────────────────────────
        q = db.query(Transaction).filter(
            Transaction.was_manually_added == False,
            Transaction.ocr_session_id.isnot(None),
        )
        if only_corrected:
            q = q.filter(Transaction.was_edited == True)

        transactions = q.all()

        # Track which session images we've already added (avoid duplicates)
        added_images = set()

        # ── Write labels ───────────────────────────────────────────────────
        labels_lines = []
        for tx in transactions:
            session_id = tx.ocr_session_id
            label = {
                "transaction_id": tx.id,
                "ocr_session_id": session_id,
                "image": f"images/{session_id}_{tx.source_image}" if tx.source_image else None,
                "ocr_extracted": {
                    "customer_name": tx.ocr_customer_name,
                    "customer_name_tamil": tx.ocr_customer_name_tamil,
                    "flower_type": tx.ocr_flower_type,
                    "weight_kg": tx.ocr_weight_kg,
                },
                "ground_truth": {
                    "customer_name": tx.customer_name,
                    "customer_name_tamil": tx.customer_name_tamil,
                    "flower_type": tx.flower_type,
                    "weight_kg": tx.weight_kg,
                },
                "corrections": tx.get_corrections(),
                "confidence": tx.ocr_confidence,
                "transaction_date": str(tx.transaction_date),
            }
            labels_lines.append(json.dumps(label, ensure_ascii=False))

            # Add image if not already added
            if tx.source_image and tx.source_image not in added_images:
                src_path = os.path.join(UPLOAD_DIR, tx.source_image)
                if os.path.exists(src_path):
                    arcname = f"images/{session_id}_{tx.source_image}"
                    zf.write(src_path, arcname)
                    added_images.add(tx.source_image)

        zf.writestr("labels.jsonl", "\n".join(labels_lines))

        # ── Write sessions ─────────────────────────────────────────────────
        session_ids = {tx.ocr_session_id for tx in transactions}
        sessions = db.query(OCRSession).filter(OCRSession.id.in_(session_ids)).all() if session_ids else []

        session_lines = []
        for s in sessions:
            session_lines.append(json.dumps({
                **s.to_dict(),
                "raw_ocr_json": s.raw_ocr_json,
            }, ensure_ascii=False))

        zf.writestr("sessions.jsonl", "\n".join(session_lines))

        # ── Stats summary ──────────────────────────────────────────────────
        stats = {
            "exported_at": datetime.utcnow().isoformat(),
            "total_transactions": len(transactions),
            "total_sessions": len(sessions),
            "total_images": len(added_images),
            "filter": "corrected_only" if only_corrected else "all_ocr",
        }
        zf.writestr("stats.json", json.dumps(stats, indent=2))

    buf.seek(0)
    return buf.read()

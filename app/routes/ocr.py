"""
OCR API Routes — v2
Now logs every OCR session and tracks user corrections vs OCR output.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from datetime import date
import uuid, os, time, asyncio
from functools import partial
from typing import Optional

from app.database import get_db
from app.services.ocr_service import run_ocr
from app.services.market_rate_service import get_rate_for_flower
from app.models.transaction import Transaction
from app.models.ocr_session import OCRSession

router = APIRouter()

UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_and_ocr(
    file: UploadFile = File(...),
    transaction_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    1. Save uploaded image
    2. Run EasyOCR pipeline
    3. Log OCR session to database
    4. Enrich parsed rows with current market rates
    5. Return preview + session_id (used at confirm time)
    """
    allowed = {"image/jpeg", "image/png", "image/jpg", "image/webp", "image/tiff"}
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}. Use JPEG/PNG/TIFF.")

    # Save file
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    # Determine transaction date
    tx_date = date.today()
    if transaction_date:
        try:
            tx_date = date.fromisoformat(transaction_date)
        except ValueError:
            pass

    # Run OCR in a thread pool so it doesn't block the asyncio event loop.
    # EasyOCR is CPU-bound / blocking — calling it directly in an async handler
    # would freeze the entire server until it finishes.
    t0 = time.perf_counter()
    loop = asyncio.get_event_loop()
    try:
        ocr_result = await asyncio.wait_for(
            loop.run_in_executor(None, partial(run_ocr, contents)),
            timeout=120,  # 2-minute hard cap; returns error instead of hanging forever
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "OCR timed out after 120 s. Try a smaller or clearer image.")
    total_ms = int((time.perf_counter() - t0) * 1000)

    # Always log the session, even if OCR failed
    session = OCRSession(
        image_filename=filename,
        image_size_bytes=len(contents),
        image_width_px=ocr_result.get("image_width"),
        image_height_px=ocr_result.get("image_height"),
        raw_ocr_json=ocr_result.get("raw_results"),
        word_count=ocr_result.get("word_count", 0),
        transaction_count=ocr_result.get("transaction_count", 0),
        avg_confidence=ocr_result.get("avg_confidence"),
        preprocessing_ms=ocr_result.get("timings", {}).get("preprocessing_ms"),
        ocr_ms=ocr_result.get("timings", {}).get("ocr_ms"),
        parsing_ms=ocr_result.get("timings", {}).get("parsing_ms"),
        total_ms=total_ms,
        status="success" if ocr_result.get("success") else "error",
        error_message=ocr_result.get("error"),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if not ocr_result["success"]:
        raise HTTPException(500, f"OCR failed: {ocr_result.get('error')}")

    # Enrich with market rates
    enriched = []
    for tx in ocr_result["transactions"]:
        rate = get_rate_for_flower(db, tx["flower_type"], tx_date)
        total = round(tx["weight_kg"] * rate, 2)
        enriched.append({
            **tx,
            "price_per_kg": rate,
            "total_amount": total,
            "transaction_date": str(tx_date),
            "source_image": filename,
            # Original OCR values — preserved through the round-trip
            "ocr_original": {
                "customer_name": tx["customer_name"],
                "customer_name_tamil": tx.get("customer_name_tamil"),
                "flower_type": tx["flower_type"],
                "weight_kg": tx["weight_kg"],
            }
        })

    return {
        "session_id": session.id,
        "filename": filename,
        "word_count": ocr_result["word_count"],
        "transaction_count": len(enriched),
        "avg_confidence": ocr_result.get("avg_confidence"),
        "total_ms": total_ms,
        "transactions": enriched,
    }


@router.post("/confirm")
async def confirm_transactions(
    payload: dict,
    db: Session = Depends(get_db),
):
    """
    Save confirmed transactions, comparing each row to its original OCR output
    to detect which fields were edited by the user.
    """
    transactions = payload.get("transactions", [])
    session_id = payload.get("session_id")
    if not transactions:
        raise HTTPException(400, "No transactions provided.")

    saved = 0
    edited_count = 0

    for tx in transactions:
        ocr_original = tx.get("ocr_original") or {}
        manually_added = tx.get("manually_added", False) or not ocr_original

        # Determine which fields differ
        edits = 0
        if not manually_added:
            if ocr_original.get("customer_name") and tx.get("customer_name") != ocr_original.get("customer_name"):
                edits += 1
            if ocr_original.get("flower_type") and tx.get("flower_type") != ocr_original.get("flower_type"):
                edits += 1
            try:
                ow = float(ocr_original.get("weight_kg") or 0)
                fw = float(tx.get("weight_kg") or 0)
                if abs(ow - fw) > 0.001:
                    edits += 1
            except (ValueError, TypeError):
                pass

        was_edited = edits > 0

        record = Transaction(
            customer_name=tx.get("customer_name", "Unknown"),
            customer_name_tamil=tx.get("customer_name_tamil"),
            flower_type=tx.get("flower_type", "Unknown"),
            flower_type_tamil=tx.get("flower_type_tamil"),
            weight_kg=float(tx.get("weight_kg", 0)),
            price_per_kg=float(tx.get("price_per_kg", 0)),
            total_amount=float(tx.get("total_amount", 0)),
            transaction_date=date.fromisoformat(tx["transaction_date"]) if tx.get("transaction_date") else date.today(),
            source_image=tx.get("source_image"),
            ocr_confidence=tx.get("ocr_confidence"),
            raw_ocr_text=tx.get("raw_text"),
            ocr_session_id=session_id,
            # Original OCR values — preserved for accuracy analysis
            ocr_customer_name=ocr_original.get("customer_name") if not manually_added else None,
            ocr_customer_name_tamil=ocr_original.get("customer_name_tamil") if not manually_added else None,
            ocr_flower_type=ocr_original.get("flower_type") if not manually_added else None,
            ocr_weight_kg=ocr_original.get("weight_kg") if not manually_added else None,
            was_edited=was_edited,
            edit_count=edits,
            was_manually_added=manually_added,
        )
        db.add(record)
        saved += 1
        if was_edited:
            edited_count += 1

    # Update session with save stats
    if session_id:
        session = db.query(OCRSession).filter(OCRSession.id == session_id).first()
        if session:
            session.saved_count = saved
            session.edited_count = edited_count

    db.commit()

    return {
        "saved": saved,
        "edited": edited_count,
        "message": f"{saved} transactions saved successfully ({edited_count} edited).",
    }

"""
Analytics Service — provides insight into OCR accuracy and user corrections.
This is the backbone of the admin review page.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case
from datetime import date, datetime, timedelta
from typing import Optional

from app.models.transaction import Transaction
from app.models.ocr_session import OCRSession
from app.models.feedback import Feedback


def get_accuracy_overview(db: Session, days: int = 30) -> dict:
    """
    High-level accuracy stats for the admin dashboard.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Sessions
    total_sessions     = db.query(func.count(OCRSession.id)).filter(OCRSession.created_at >= since).scalar() or 0
    successful_sessions= db.query(func.count(OCRSession.id)).filter(OCRSession.created_at >= since, OCRSession.status == "success").scalar() or 0
    failed_sessions    = db.query(func.count(OCRSession.id)).filter(OCRSession.created_at >= since, OCRSession.status == "error").scalar() or 0

    # Transactions from those sessions
    total_txs       = db.query(func.count(Transaction.id)).filter(Transaction.created_at >= since).scalar() or 0
    edited_txs      = db.query(func.count(Transaction.id)).filter(Transaction.created_at >= since, Transaction.was_edited == True).scalar() or 0
    manual_txs      = db.query(func.count(Transaction.id)).filter(Transaction.created_at >= since, Transaction.was_manually_added == True).scalar() or 0
    ocr_txs         = total_txs - manual_txs

    # Edit rate (fraction of OCR-derived transactions that needed correction)
    edit_rate = (edited_txs / ocr_txs) if ocr_txs > 0 else 0

    # Average confidence
    avg_conf_q = db.query(func.avg(OCRSession.avg_confidence)).filter(
        OCRSession.created_at >= since, OCRSession.avg_confidence.isnot(None)
    ).scalar()
    avg_confidence = round(avg_conf_q, 3) if avg_conf_q else 0

    # Open feedback
    open_feedback = db.query(func.count(Feedback.id)).filter(Feedback.status == "open").scalar() or 0

    # Average OCR timing
    avg_total_ms = db.query(func.avg(OCRSession.total_ms)).filter(
        OCRSession.created_at >= since, OCRSession.total_ms.isnot(None)
    ).scalar()
    avg_total_ms = int(avg_total_ms) if avg_total_ms else 0

    return {
        "period_days": days,
        "total_sessions": total_sessions,
        "successful_sessions": successful_sessions,
        "failed_sessions": failed_sessions,
        "total_transactions": total_txs,
        "ocr_transactions": ocr_txs,
        "manual_transactions": manual_txs,
        "edited_transactions": edited_txs,
        "edit_rate_percent": round(edit_rate * 100, 1),
        "avg_confidence_percent": round(avg_confidence * 100, 1),
        "avg_ocr_time_ms": avg_total_ms,
        "open_feedback": open_feedback,
    }


def get_field_accuracy(db: Session, days: int = 30) -> dict:
    """
    For each field (customer_name, flower_type, weight_kg), what % of OCR-derived
    transactions had that field edited?
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Only consider OCR-derived transactions (not manually added)
    base = db.query(Transaction).filter(
        Transaction.created_at >= since,
        Transaction.was_manually_added == False,
        Transaction.ocr_session_id.isnot(None),
    )
    total = base.count()

    if total == 0:
        return {"total": 0, "fields": []}

    name_edits = base.filter(
        Transaction.ocr_customer_name.isnot(None),
        Transaction.customer_name != Transaction.ocr_customer_name,
    ).count()

    flower_edits = base.filter(
        Transaction.ocr_flower_type.isnot(None),
        Transaction.flower_type != Transaction.ocr_flower_type,
    ).count()

    # Weight: float comparison with tolerance
    weight_edits = sum(
        1 for tx in base.filter(Transaction.ocr_weight_kg.isnot(None)).all()
        if abs((tx.weight_kg or 0) - (tx.ocr_weight_kg or 0)) > 0.001
    )

    def stat(edits):
        return {
            "edits": edits,
            "accuracy_percent": round((1 - edits / total) * 100, 1) if total else 0,
            "edit_rate_percent": round(edits / total * 100, 1) if total else 0,
        }

    return {
        "total": total,
        "fields": [
            {"field": "customer_name", **stat(name_edits)},
            {"field": "flower_type",   **stat(flower_edits)},
            {"field": "weight_kg",     **stat(weight_edits)},
        ],
    }


def get_flower_accuracy(db: Session, days: int = 30) -> list[dict]:
    """
    Per-flower accuracy: for each flower, how often was it correctly identified?
    """
    since = datetime.utcnow() - timedelta(days=days)

    rows = db.query(
        Transaction.flower_type,
        func.count(Transaction.id).label("total"),
        func.sum(case((Transaction.was_edited == True, 1), else_=0)).label("edited"),
        func.avg(Transaction.ocr_confidence).label("avg_conf"),
    ).filter(
        Transaction.created_at >= since,
        Transaction.was_manually_added == False,
        Transaction.ocr_session_id.isnot(None),
    ).group_by(Transaction.flower_type).all()

    return [
        {
            "flower_type": r.flower_type,
            "total": r.total,
            "edited": r.edited or 0,
            "accuracy_percent": round((1 - (r.edited or 0) / r.total) * 100, 1) if r.total else 0,
            "avg_confidence_percent": round((r.avg_conf or 0) * 100, 1),
        }
        for r in sorted(rows, key=lambda r: -r.total)
    ]


def get_low_confidence_transactions(db: Session, threshold: float = 0.6, limit: int = 50) -> list[dict]:
    """List transactions where OCR confidence was below threshold — good candidates for review."""
    txs = (
        db.query(Transaction)
        .filter(Transaction.ocr_confidence != None, Transaction.ocr_confidence < threshold)
        .order_by(Transaction.ocr_confidence.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            **t.to_dict(),
            "corrections": t.get_corrections(),
        }
        for t in txs
    ]


def get_corrected_transactions(db: Session, limit: int = 100) -> list[dict]:
    """List transactions where users had to correct OCR output — for retraining data."""
    txs = (
        db.query(Transaction)
        .filter(Transaction.was_edited == True, Transaction.was_manually_added == False)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            **t.to_dict(),
            "corrections": t.get_corrections(),
        }
        for t in txs
    ]


def get_failed_sessions(db: Session, limit: int = 50) -> list[dict]:
    """OCR sessions that crashed — bugs to investigate."""
    sessions = (
        db.query(OCRSession)
        .filter(OCRSession.status == "error")
        .order_by(OCRSession.created_at.desc())
        .limit(limit)
        .all()
    )
    return [s.to_dict() for s in sessions]


def get_session_with_transactions(db: Session, session_id: int) -> Optional[dict]:
    """Detailed view of one OCR session, including all transactions saved from it."""
    s = db.query(OCRSession).filter(OCRSession.id == session_id).first()
    if not s:
        return None

    related_txs = (
        db.query(Transaction)
        .filter(Transaction.ocr_session_id == session_id)
        .all()
    )

    return {
        **s.to_dict(),
        "raw_ocr_json": s.raw_ocr_json,
        "transactions": [{**t.to_dict(), "corrections": t.get_corrections()} for t in related_txs],
    }

"""
Admin Routes — review page, export, feedback management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.services import analytics_service, export_service
from app.models.feedback import Feedback

router = APIRouter()


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/overview")
def overview(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return analytics_service.get_accuracy_overview(db, days)


@router.get("/field-accuracy")
def field_accuracy(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return analytics_service.get_field_accuracy(db, days)


@router.get("/flower-accuracy")
def flower_accuracy(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return analytics_service.get_flower_accuracy(db, days)


@router.get("/low-confidence")
def low_confidence(threshold: float = Query(0.6, ge=0, le=1),
                   limit: int = Query(50, ge=1, le=500),
                   db: Session = Depends(get_db)):
    return analytics_service.get_low_confidence_transactions(db, threshold, limit)


@router.get("/corrected")
def corrected(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return analytics_service.get_corrected_transactions(db, limit)


@router.get("/failed-sessions")
def failed_sessions(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return analytics_service.get_failed_sessions(db, limit)


@router.get("/sessions/{session_id}")
def session_detail(session_id: int, db: Session = Depends(get_db)):
    s = analytics_service.get_session_with_transactions(db, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/export")
def export_data(only_corrected: bool = Query(True), db: Session = Depends(get_db)):
    """Download a ZIP of training data (images + labels)."""
    zip_bytes = export_service.export_training_data(db, only_corrected=only_corrected)
    filename = f"tamil-ocr-training-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    transaction_id: Optional[int] = None
    ocr_session_id: Optional[int] = None
    issue_type: str
    description: Optional[str] = None


@router.post("/feedback")
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    if not payload.transaction_id and not payload.ocr_session_id:
        raise HTTPException(400, "Either transaction_id or ocr_session_id is required")

    fb = Feedback(
        transaction_id=payload.transaction_id,
        ocr_session_id=payload.ocr_session_id,
        issue_type=payload.issue_type,
        description=payload.description,
        status="open",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb.to_dict()


@router.get("/feedback")
def list_feedback(status: str = Query("open"), db: Session = Depends(get_db)):
    items = db.query(Feedback).filter(Feedback.status == status).order_by(Feedback.created_at.desc()).all()
    return {"feedback": [f.to_dict() for f in items], "count": len(items)}


class FeedbackUpdate(BaseModel):
    status: str  # open | reviewed | resolved
    resolution_note: Optional[str] = None


@router.put("/feedback/{feedback_id}")
def update_feedback(feedback_id: int, payload: FeedbackUpdate, db: Session = Depends(get_db)):
    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(404, "Feedback not found")
    fb.status = payload.status
    fb.resolution_note = payload.resolution_note
    if payload.status == "resolved":
        fb.resolved_at = datetime.utcnow()
    db.commit()
    return fb.to_dict()

"""
User Feedback Model
Stores user-submitted issue reports against transactions or OCR sessions.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)

    # What is being reported (one of these is set)
    transaction_id   = Column(Integer, ForeignKey("transactions.id"), nullable=True, index=True)
    ocr_session_id   = Column(Integer, ForeignKey("ocr_sessions.id"), nullable=True, index=True)

    # Issue details
    issue_type       = Column(String(50), nullable=False)
    # one of: wrong_name, wrong_flower, wrong_weight, wrong_price,
    #         missed_row, extra_row, image_quality, other

    description      = Column(Text, nullable=True)

    # Status
    status           = Column(String(20), default="open")    # open | reviewed | resolved
    resolution_note  = Column(Text, nullable=True)

    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at      = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "ocr_session_id": self.ocr_session_id,
            "issue_type": self.issue_type,
            "description": self.description,
            "status": self.status,
            "resolution_note": self.resolution_note,
            "created_at": str(self.created_at),
            "resolved_at": str(self.resolved_at) if self.resolved_at else None,
        }

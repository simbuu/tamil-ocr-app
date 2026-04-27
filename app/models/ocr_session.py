"""
OCR Session Model
Logs every OCR run — image, raw output, timing, parsed result.
This is the foundation for analysing OCR accuracy across real customer data.
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class OCRSession(Base):
    __tablename__ = "ocr_sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Image reference
    image_filename     = Column(String(500), nullable=False)
    image_size_bytes   = Column(Integer, nullable=True)
    image_width_px     = Column(Integer, nullable=True)
    image_height_px    = Column(Integer, nullable=True)

    # OCR output
    raw_ocr_json       = Column(JSON, nullable=True)        # full bbox + text + confidence list
    word_count         = Column(Integer, default=0)
    transaction_count  = Column(Integer, default=0)         # rows successfully parsed
    avg_confidence     = Column(Float, nullable=True)

    # Timing
    preprocessing_ms   = Column(Integer, nullable=True)
    ocr_ms             = Column(Integer, nullable=True)
    parsing_ms         = Column(Integer, nullable=True)
    total_ms           = Column(Integer, nullable=True)

    # Status
    status             = Column(String(50), default="success")   # success | error | partial
    error_message      = Column(Text, nullable=True)

    # User behaviour
    saved_count        = Column(Integer, default=0)         # how many were finally saved
    edited_count       = Column(Integer, default=0)         # how many user-edited before save

    created_at         = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "image_filename": self.image_filename,
            "image_size_bytes": self.image_size_bytes,
            "word_count": self.word_count,
            "transaction_count": self.transaction_count,
            "avg_confidence": self.avg_confidence,
            "total_ms": self.total_ms,
            "status": self.status,
            "error_message": self.error_message,
            "saved_count": self.saved_count,
            "edited_count": self.edited_count,
            "created_at": str(self.created_at),
        }

"""
Transaction Model — v2 with correction tracking
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    # Customer info (final saved values)
    customer_name = Column(String(200), nullable=False, index=True)
    customer_name_tamil = Column(String(200), nullable=True)

    # Flower details (final saved values)
    flower_type = Column(String(100), nullable=False, index=True)
    flower_type_tamil = Column(String(100), nullable=True)

    # Weight & pricing (final saved values)
    weight_kg = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)

    # Date
    transaction_date = Column(Date, nullable=False, index=True)

    # OCR metadata
    source_image = Column(String(500), nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    ocr_session_id = Column(Integer, ForeignKey("ocr_sessions.id"), nullable=True, index=True)

    # ── NEW: OCR-extracted original values (for accuracy analysis) ──────────
    # These store what OCR ORIGINALLY produced, before any user edits.
    # Comparing these to the final values above tells us:
    #   - Which fields users had to correct
    #   - How accurate OCR is per field type
    #   - Which flowers/customers OCR struggles with
    ocr_customer_name        = Column(String(200), nullable=True)
    ocr_customer_name_tamil  = Column(String(200), nullable=True)
    ocr_flower_type          = Column(String(100), nullable=True)
    ocr_weight_kg            = Column(Float, nullable=True)

    # Was this transaction edited by user before saving?
    was_edited     = Column(Boolean, default=False, index=True)
    edit_count     = Column(Integer, default=0)
    was_manually_added = Column(Boolean, default=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_name_tamil": self.customer_name_tamil,
            "flower_type": self.flower_type,
            "flower_type_tamil": self.flower_type_tamil,
            "weight_kg": self.weight_kg,
            "price_per_kg": self.price_per_kg,
            "total_amount": self.total_amount,
            "transaction_date": str(self.transaction_date),
            "source_image": self.source_image,
            "ocr_confidence": self.ocr_confidence,
            "ocr_session_id": self.ocr_session_id,
            "ocr_customer_name": self.ocr_customer_name,
            "ocr_customer_name_tamil": self.ocr_customer_name_tamil,
            "ocr_flower_type": self.ocr_flower_type,
            "ocr_weight_kg": self.ocr_weight_kg,
            "was_edited": self.was_edited,
            "edit_count": self.edit_count,
            "was_manually_added": self.was_manually_added,
            "created_at": str(self.created_at),
        }

    def get_corrections(self) -> list[dict]:
        """Fields edited from OCR output to final saved value."""
        corrections = []
        if self.was_manually_added:
            return []
        if self.ocr_customer_name and self.customer_name != self.ocr_customer_name:
            corrections.append({"field": "customer_name", "ocr": self.ocr_customer_name, "saved": self.customer_name})
        if self.ocr_flower_type and self.flower_type != self.ocr_flower_type:
            corrections.append({"field": "flower_type", "ocr": self.ocr_flower_type, "saved": self.flower_type})
        if self.ocr_weight_kg is not None and abs((self.weight_kg or 0) - self.ocr_weight_kg) > 0.001:
            corrections.append({"field": "weight_kg", "ocr": self.ocr_weight_kg, "saved": self.weight_kg})
        return corrections

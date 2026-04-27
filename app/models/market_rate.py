"""
Market Rate Model - stores per-flower daily pricing
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class MarketRate(Base):
    __tablename__ = "market_rates"

    id = Column(Integer, primary_key=True, index=True)
    flower_type = Column(String(100), nullable=False, index=True)
    flower_type_tamil = Column(String(100), nullable=True)
    price_per_kg = Column(Float, nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "flower_type": self.flower_type,
            "flower_type_tamil": self.flower_type_tamil,
            "price_per_kg": self.price_per_kg,
            "effective_date": str(self.effective_date),
            "is_active": self.is_active,
        }

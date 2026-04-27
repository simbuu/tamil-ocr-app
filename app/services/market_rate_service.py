"""
Market Rate Service - manage flower pricing
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date
from app.models.market_rate import MarketRate
from app.database import SessionLocal


DEFAULT_RATES = [
    {"flower_type": "Rose", "flower_type_tamil": "ரோஜா", "price_per_kg": 120.0},
    {"flower_type": "Jasmine", "flower_type_tamil": "மல்லிகை", "price_per_kg": 350.0},
    {"flower_type": "Marigold", "flower_type_tamil": "சேவந்தி", "price_per_kg": 80.0},
    {"flower_type": "Lotus", "flower_type_tamil": "தாமரை", "price_per_kg": 200.0},
    {"flower_type": "Crossandra", "flower_type_tamil": "கனகாம்பரம்", "price_per_kg": 450.0},
    {"flower_type": "Tuberose", "flower_type_tamil": "நிலாம்பரி", "price_per_kg": 180.0},
    {"flower_type": "Chrysanthemum", "flower_type_tamil": "சந்தி பூ", "price_per_kg": 60.0},
    {"flower_type": "Lily", "flower_type_tamil": "லில்லி", "price_per_kg": 250.0},
]


def seed_default_rates():
    """Insert default rates on first run."""
    db = SessionLocal()
    try:
        existing = db.query(MarketRate).count()
        if existing == 0:
            today = date.today()
            for r in DEFAULT_RATES:
                rate = MarketRate(
                    flower_type=r["flower_type"],
                    flower_type_tamil=r["flower_type_tamil"],
                    price_per_kg=r["price_per_kg"],
                    effective_date=today,
                    is_active=True,
                )
                db.add(rate)
            db.commit()
    finally:
        db.close()


def get_rate_for_flower(db: Session, flower_type: str, on_date: date = None) -> float:
    """Get the most recent active price for a flower type."""
    if on_date is None:
        on_date = date.today()

    rate = (
        db.query(MarketRate)
        .filter(
            MarketRate.flower_type.ilike(f"%{flower_type}%"),
            MarketRate.is_active == True,
            MarketRate.effective_date <= on_date,
        )
        .order_by(desc(MarketRate.effective_date))
        .first()
    )
    return rate.price_per_kg if rate else 0.0


def get_all_active_rates(db: Session) -> list:
    """Return the latest active rate per flower type."""
    from sqlalchemy import func

    subq = (
        db.query(
            MarketRate.flower_type,
            func.max(MarketRate.effective_date).label("max_date"),
        )
        .filter(MarketRate.is_active == True)
        .group_by(MarketRate.flower_type)
        .subquery()
    )

    rates = (
        db.query(MarketRate)
        .join(
            subq,
            (MarketRate.flower_type == subq.c.flower_type)
            & (MarketRate.effective_date == subq.c.max_date),
        )
        .all()
    )
    return rates

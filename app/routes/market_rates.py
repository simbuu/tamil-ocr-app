"""
Market Rates API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.market_rate import MarketRate
from app.services.market_rate_service import get_all_active_rates

router = APIRouter()


class RateCreate(BaseModel):
    flower_type: str
    flower_type_tamil: Optional[str] = None
    price_per_kg: float
    effective_date: Optional[date] = None


@router.get("/")
def list_rates(db: Session = Depends(get_db)):
    rates = get_all_active_rates(db)
    return {"rates": [r.to_dict() for r in rates]}


@router.post("/")
def create_rate(payload: RateCreate, db: Session = Depends(get_db)):
    rate = MarketRate(
        flower_type=payload.flower_type,
        flower_type_tamil=payload.flower_type_tamil,
        price_per_kg=payload.price_per_kg,
        effective_date=payload.effective_date or date.today(),
        is_active=True,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate.to_dict()


@router.put("/{rate_id}")
def update_rate(rate_id: int, payload: RateCreate, db: Session = Depends(get_db)):
    rate = db.query(MarketRate).filter(MarketRate.id == rate_id).first()
    if not rate:
        raise HTTPException(404, "Rate not found")
    rate.price_per_kg = payload.price_per_kg
    rate.effective_date = payload.effective_date or date.today()
    db.commit()
    return rate.to_dict()


@router.delete("/{rate_id}")
def delete_rate(rate_id: int, db: Session = Depends(get_db)):
    rate = db.query(MarketRate).filter(MarketRate.id == rate_id).first()
    if not rate:
        raise HTTPException(404, "Rate not found")
    rate.is_active = False
    db.commit()
    return {"deactivated": rate_id}

"""
Transactions API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.services.transaction_service import (
    get_transactions, get_transaction_by_id,
    create_transaction, delete_transaction, get_dashboard_stats,
)
from app.services.market_rate_service import get_rate_for_flower

router = APIRouter()


class TransactionCreate(BaseModel):
    customer_name: str
    customer_name_tamil: Optional[str] = None
    flower_type: str
    flower_type_tamil: Optional[str] = None
    weight_kg: float
    price_per_kg: Optional[float] = None   # auto-looked up if omitted
    transaction_date: Optional[date] = None


@router.post("/")
def add_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    """Manually create a transaction (used by Quick Entry)."""
    if payload.weight_kg <= 0:
        raise HTTPException(400, "weight_kg must be positive")
    txn_date = payload.transaction_date or date.today()
    price = payload.price_per_kg
    if price is None or price <= 0:
        price = get_rate_for_flower(db, payload.flower_type, txn_date)
    total = round(payload.weight_kg * price, 2)
    tx = create_transaction(db, {
        "customer_name": payload.customer_name.strip(),
        "customer_name_tamil": (payload.customer_name_tamil or "").strip() or None,
        "flower_type": payload.flower_type.strip(),
        "flower_type_tamil": (payload.flower_type_tamil or "").strip() or None,
        "weight_kg": payload.weight_kg,
        "price_per_kg": price,
        "total_amount": total,
        "transaction_date": txn_date,
        "was_manually_added": True,
    })
    return tx.to_dict()


@router.get("/")
def list_transactions(
    customer_name: Optional[str] = Query(None),
    flower_type: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    txs = get_transactions(db, customer_name, flower_type, start_date, end_date, skip, limit)
    return {"transactions": [t.to_dict() for t in txs], "count": len(txs)}


@router.get("/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    return get_dashboard_stats(db)


@router.get("/{tx_id}")
def get_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = get_transaction_by_id(db, tx_id)
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return tx.to_dict()


@router.delete("/{tx_id}")
def remove_transaction(tx_id: int, db: Session = Depends(get_db)):
    ok = delete_transaction(db, tx_id)
    if not ok:
        raise HTTPException(404, "Transaction not found")
    return {"deleted": tx_id}

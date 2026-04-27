"""
Transactions API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.database import get_db
from app.services.transaction_service import (
    get_transactions, get_transaction_by_id,
    delete_transaction, get_dashboard_stats,
)

router = APIRouter()


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

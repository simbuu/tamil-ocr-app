"""
Loan / Advance Account API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.services import loan_service

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    customer_name:       str
    customer_name_tamil: Optional[str] = None
    customer_id:         Optional[int] = None
    interest_rate:       float = 2.0
    notes:               Optional[str] = None

class TransactionCreate(BaseModel):
    transaction_type: str          # borrow | repay | interest
    amount:           float
    transaction_date: Optional[date] = None
    notes:            Optional[str]  = None

class InterestApply(BaseModel):
    on_date: Optional[date] = None


# ── Account endpoints ─────────────────────────────────────────────────────────

@router.get("/")
def list_accounts(db: Session = Depends(get_db)):
    return loan_service.get_all_accounts(db)


@router.get("/summary")
def accounts_summary(db: Session = Depends(get_db)):
    return loan_service.get_accounts_summary(db)


@router.post("/")
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    name = (payload.customer_name or "").strip()
    if not name:
        raise HTTPException(400, "customer_name is required")
    if payload.interest_rate < 0:
        raise HTTPException(400, "interest_rate must be >= 0")
    acc = loan_service.create_account(db, {
        "customer_name":       name,
        "customer_name_tamil": (payload.customer_name_tamil or "").strip() or None,
        "customer_id":         payload.customer_id,
        "interest_rate":       payload.interest_rate,
        "notes":               (payload.notes or "").strip() or None,
    })
    b = loan_service._balance(db, acc.id)
    return acc.to_dict(**b)


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    result = loan_service.get_account_with_balance(db, account_id)
    if not result:
        raise HTTPException(404, "Account not found")
    return result


@router.patch("/{account_id}/status")
def update_status(account_id: int, payload: dict, db: Session = Depends(get_db)):
    status = payload.get("status")
    if status not in ("active", "closed"):
        raise HTTPException(400, "status must be 'active' or 'closed'")
    acc = loan_service.update_account_status(db, account_id, status)
    if not acc:
        raise HTTPException(404, "Account not found")
    b = loan_service._balance(db, acc.id)
    return acc.to_dict(**b)


# ── Transaction endpoints ─────────────────────────────────────────────────────

@router.get("/{account_id}/transactions")
def list_transactions(account_id: int, db: Session = Depends(get_db)):
    acc = loan_service.get_account(db, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    txns = loan_service.get_transactions(db, account_id)
    return [t.to_dict() for t in txns]


@router.post("/{account_id}/transactions")
def add_transaction(account_id: int, payload: TransactionCreate,
                    db: Session = Depends(get_db)):
    acc = loan_service.get_account(db, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    if payload.transaction_type not in ("borrow", "repay", "interest"):
        raise HTTPException(400, "transaction_type must be borrow, repay, or interest")
    if payload.amount <= 0:
        raise HTTPException(400, "amount must be positive")
    txn = loan_service.add_transaction(db, account_id, {
        "transaction_type": payload.transaction_type,
        "amount":           payload.amount,
        "transaction_date": payload.transaction_date or date.today(),
        "notes":            (payload.notes or "").strip() or None,
    })
    return txn.to_dict()


@router.post("/{account_id}/apply-interest")
def apply_interest(account_id: int, payload: InterestApply,
                   db: Session = Depends(get_db)):
    txn = loan_service.apply_monthly_interest(db, account_id, payload.on_date)
    if txn is None:
        raise HTTPException(400, "No outstanding balance or account is closed")
    return txn.to_dict()


# ── Monthly bill ──────────────────────────────────────────────────────────────

@router.get("/bill/{customer_name}")
def monthly_bill(
    customer_name: str,
    year:  int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db),
):
    if not (1 <= month <= 12):
        raise HTTPException(400, "month must be 1-12")
    return loan_service.get_monthly_bill(db, customer_name, year, month)

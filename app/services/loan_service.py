"""
Loan / Advance Account Service

Business rules
--------------
• balance = total_borrowed + total_interest - total_repaid
• apply_monthly_interest: charges (balance × rate/100) as a new 'interest' entry
• monthly_bill: shows flower earnings for a month alongside the outstanding
  balance so the owner can decide how much to deduct and record it as a repayment
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from typing import Optional

from app.models.loan import LoanAccount, LoanTransaction
from app.models.transaction import Transaction


# ── helpers ───────────────────────────────────────────────────────────────────

def _balance(db: Session, account_id: int) -> dict:
    """Return debit / credit totals and net balance for an account."""
    rows = (
        db.query(LoanTransaction.transaction_type,
                 func.sum(LoanTransaction.amount).label("total"))
        .filter(LoanTransaction.account_id == account_id)
        .group_by(LoanTransaction.transaction_type)
        .all()
    )
    totals = {r.transaction_type: r.total for r in rows}
    borrowed  = totals.get("borrow",   0.0)
    interest  = totals.get("interest", 0.0)
    repaid    = totals.get("repay",    0.0)
    return {
        "total_borrowed": borrowed,
        "total_interest": interest,
        "total_repaid":   repaid,
        "balance":        borrowed + interest - repaid,
    }


# ── accounts ──────────────────────────────────────────────────────────────────

def get_all_accounts(db: Session) -> list:
    accounts = (
        db.query(LoanAccount)
        .order_by(LoanAccount.customer_name)
        .all()
    )
    result = []
    for acc in accounts:
        b = _balance(db, acc.id)
        result.append(acc.to_dict(**b))
    return result


def get_account(db: Session, account_id: int) -> Optional[LoanAccount]:
    return db.query(LoanAccount).filter(LoanAccount.id == account_id).first()


def get_account_with_balance(db: Session, account_id: int) -> Optional[dict]:
    acc = get_account(db, account_id)
    if not acc:
        return None
    b = _balance(db, acc.id)
    return acc.to_dict(**b)


def create_account(db: Session, data: dict) -> LoanAccount:
    acc = LoanAccount(**data)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def update_account_status(db: Session, account_id: int, status: str) -> Optional[LoanAccount]:
    acc = get_account(db, account_id)
    if acc:
        acc.status = status
        db.commit()
    return acc


# ── transactions ──────────────────────────────────────────────────────────────

def get_transactions(db: Session, account_id: int) -> list:
    return (
        db.query(LoanTransaction)
        .filter(LoanTransaction.account_id == account_id)
        .order_by(LoanTransaction.transaction_date.desc(),
                  LoanTransaction.created_at.desc())
        .all()
    )


def add_transaction(db: Session, account_id: int, data: dict) -> LoanTransaction:
    txn = LoanTransaction(account_id=account_id, **data)
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def apply_monthly_interest(db: Session, account_id: int,
                            on_date: date = None) -> Optional[LoanTransaction]:
    """Charge (outstanding_balance × interest_rate/100) as a new interest entry."""
    acc = get_account(db, account_id)
    if not acc or acc.status != "active":
        return None
    b = _balance(db, account_id)
    outstanding = b["balance"]
    if outstanding <= 0:
        return None
    interest_amount = round(outstanding * acc.interest_rate / 100, 2)
    txn = LoanTransaction(
        account_id       = account_id,
        transaction_type = "interest",
        amount           = interest_amount,
        transaction_date = on_date or date.today(),
        notes            = f"Monthly interest @ {acc.interest_rate}% on ₹{outstanding:.2f}",
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


# ── monthly bill ──────────────────────────────────────────────────────────────

def get_monthly_bill(db: Session, customer_name: str, year: int, month: int) -> dict:
    """
    Combine flower earnings for the month with the current loan balance
    to produce a single billing summary.
    """
    from calendar import monthrange
    first_day = date(year, month, 1)
    last_day  = date(year, month, monthrange(year, month)[1])

    # ── Flower earnings this month ─────────────────────────────────────────
    flower_rows = (
        db.query(
            Transaction.flower_type,
            func.sum(Transaction.weight_kg).label("weight"),
            func.sum(Transaction.total_amount).label("amount"),
            func.count(Transaction.id).label("count"),
        )
        .filter(
            Transaction.customer_name.ilike(f"%{customer_name}%"),
            Transaction.transaction_date >= first_day,
            Transaction.transaction_date <= last_day,
        )
        .group_by(Transaction.flower_type)
        .all()
    )
    flower_lines = [
        {
            "flower_type": r.flower_type,
            "weight_kg":   round(r.weight, 2),
            "amount":      round(r.amount, 2),
            "count":       r.count,
        }
        for r in flower_rows
    ]
    total_earnings = sum(r["amount"] for r in flower_lines)

    # ── Loan account ───────────────────────────────────────────────────────
    acc = (
        db.query(LoanAccount)
        .filter(LoanAccount.customer_name.ilike(f"%{customer_name}%"),
                LoanAccount.status == "active")
        .first()
    )
    account_info  = None
    loan_balance  = 0.0
    if acc:
        b = _balance(db, acc.id)
        loan_balance = b["balance"]
        account_info = acc.to_dict(**b)

    # ── Repayments already recorded this month ────────────────────────────
    monthly_repaid = 0.0
    if acc:
        monthly_repaid = (
            db.query(func.sum(LoanTransaction.amount))
            .filter(
                LoanTransaction.account_id       == acc.id,
                LoanTransaction.transaction_type == "repay",
                LoanTransaction.transaction_date >= first_day,
                LoanTransaction.transaction_date <= last_day,
            )
            .scalar() or 0.0
        )

    net_payable = total_earnings - monthly_repaid

    return {
        "customer_name":  customer_name,
        "year":           year,
        "month":          month,
        "flower_lines":   flower_lines,
        "total_earnings": round(total_earnings, 2),
        "loan_account":   account_info,
        "loan_balance":   round(loan_balance, 2),
        "monthly_repaid": round(monthly_repaid, 2),
        "net_payable":    round(net_payable, 2),
    }


def get_accounts_summary(db: Session) -> dict:
    """Dashboard-level numbers."""
    all_accounts = db.query(LoanAccount).filter(LoanAccount.status == "active").all()
    total_outstanding = 0.0
    for acc in all_accounts:
        b = _balance(db, acc.id)
        total_outstanding += b["balance"]
    return {
        "active_accounts":   len(all_accounts),
        "total_outstanding": round(total_outstanding, 2),
    }

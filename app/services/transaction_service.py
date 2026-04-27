"""
Transaction Service - CRUD + analytics
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date, timedelta
from typing import Optional
from app.models.transaction import Transaction


def create_transaction(db: Session, data: dict) -> Transaction:
    tx = Transaction(**data)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def bulk_create_transactions(db: Session, records: list[dict]) -> list[Transaction]:
    txs = [Transaction(**r) for r in records]
    db.bulk_save_objects(txs)
    db.commit()
    return txs


def get_transactions(
    db: Session,
    customer_name: Optional[str] = None,
    flower_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Transaction]:
    q = db.query(Transaction)
    if customer_name:
        q = q.filter(Transaction.customer_name.ilike(f"%{customer_name}%"))
    if flower_type:
        q = q.filter(Transaction.flower_type.ilike(f"%{flower_type}%"))
    if start_date:
        q = q.filter(Transaction.transaction_date >= start_date)
    if end_date:
        q = q.filter(Transaction.transaction_date <= end_date)
    return q.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()


def get_transaction_by_id(db: Session, tx_id: int) -> Optional[Transaction]:
    return db.query(Transaction).filter(Transaction.id == tx_id).first()


def delete_transaction(db: Session, tx_id: int) -> bool:
    tx = get_transaction_by_id(db, tx_id)
    if tx:
        db.delete(tx)
        db.commit()
        return True
    return False


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_daily_summary(db: Session, on_date: date) -> dict:
    """Aggregate totals for a single day."""
    results = (
        db.query(
            Transaction.flower_type,
            func.sum(Transaction.weight_kg).label("total_weight"),
            func.sum(Transaction.total_amount).label("total_amount"),
            func.count(Transaction.id).label("count"),
        )
        .filter(Transaction.transaction_date == on_date)
        .group_by(Transaction.flower_type)
        .all()
    )
    return {
        "date": str(on_date),
        "flowers": [
            {
                "flower_type": r.flower_type,
                "total_weight_kg": round(r.total_weight, 2),
                "total_amount": round(r.total_amount, 2),
                "transaction_count": r.count,
            }
            for r in results
        ],
        "grand_total": round(sum(r.total_amount for r in results), 2),
    }


def get_monthly_summary(db: Session, year: int, month: int) -> dict:
    """Aggregate totals for an entire month."""
    results = (
        db.query(
            Transaction.flower_type,
            func.sum(Transaction.weight_kg).label("total_weight"),
            func.sum(Transaction.total_amount).label("total_amount"),
            func.count(Transaction.id).label("count"),
        )
        .filter(
            extract("year", Transaction.transaction_date) == year,
            extract("month", Transaction.transaction_date) == month,
        )
        .group_by(Transaction.flower_type)
        .all()
    )
    return {
        "year": year,
        "month": month,
        "flowers": [
            {
                "flower_type": r.flower_type,
                "total_weight_kg": round(r.total_weight, 2),
                "total_amount": round(r.total_amount, 2),
                "transaction_count": r.count,
            }
            for r in results
        ],
        "grand_total": round(sum(r.total_amount for r in results), 2),
    }


def get_customer_report(db: Session, customer_name: str) -> dict:
    """Full history + totals for one customer."""
    txs = (
        db.query(Transaction)
        .filter(Transaction.customer_name.ilike(f"%{customer_name}%"))
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
    total_weight = sum(t.weight_kg for t in txs)
    total_amount = sum(t.total_amount for t in txs)
    return {
        "customer_name": customer_name,
        "transaction_count": len(txs),
        "total_weight_kg": round(total_weight, 2),
        "total_amount": round(total_amount, 2),
        "transactions": [t.to_dict() for t in txs],
    }


def get_dashboard_stats(db: Session) -> dict:
    """High-level stats for the home dashboard."""
    today = date.today()
    week_ago = today - timedelta(days=7)

    total_txs = db.query(func.count(Transaction.id)).scalar() or 0
    total_revenue = db.query(func.sum(Transaction.total_amount)).scalar() or 0.0
    total_customers = db.query(func.count(func.distinct(Transaction.customer_name))).scalar() or 0
    weekly_revenue = (
        db.query(func.sum(Transaction.total_amount))
        .filter(Transaction.transaction_date >= week_ago)
        .scalar()
        or 0.0
    )

    # Top flower by weight
    top_flower = (
        db.query(Transaction.flower_type, func.sum(Transaction.weight_kg).label("w"))
        .group_by(Transaction.flower_type)
        .order_by(func.sum(Transaction.weight_kg).desc())
        .first()
    )

    return {
        "total_transactions": total_txs,
        "total_revenue": round(total_revenue, 2),
        "total_customers": total_customers,
        "weekly_revenue": round(weekly_revenue, 2),
        "top_flower": top_flower.flower_type if top_flower else "-",
    }

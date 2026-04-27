"""
Reports API Routes - returns JSON or PDF
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.database import get_db
from app.services.transaction_service import (
    get_daily_summary, get_monthly_summary, get_customer_report,
)
from app.services.report_service import (
    generate_customer_report_pdf, generate_monthly_report_pdf,
    generate_transaction_template_pdf,
)

router = APIRouter()


@router.get("/daily")
def daily_report(on_date: Optional[date] = Query(None), db: Session = Depends(get_db)):
    target = on_date or date.today()
    return get_daily_summary(db, target)


@router.get("/monthly")
def monthly_report(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
):
    today = date.today()
    return get_monthly_summary(db, year or today.year, month or today.month)


@router.get("/customer")
def customer_report(name: str = Query(...), db: Session = Depends(get_db)):
    return get_customer_report(db, name)


# ── PDF endpoints ─────────────────────────────────────────────────────────────

@router.get("/customer/pdf")
def customer_report_pdf(name: str = Query(...), db: Session = Depends(get_db)):
    data = get_customer_report(db, name)
    pdf_bytes = generate_customer_report_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="customer_{name}.pdf"'},
    )


@router.get("/template/pdf")
def transaction_template_pdf():
    """Download a blank printable transaction template for handwriting."""
    pdf_bytes = generate_transaction_template_pdf()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="flower_transaction_template.pdf"'},
    )


@router.get("/monthly/pdf")
def monthly_report_pdf(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
):
    today = date.today()
    data = get_monthly_summary(db, year or today.year, month or today.month)
    pdf_bytes = generate_monthly_report_pdf(data)
    filename = f"monthly_{data['year']}_{data['month']:02d}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

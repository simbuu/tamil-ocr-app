"""
Customer management API routes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer

router = APIRouter()


@router.get("/")
def list_customers(db: Session = Depends(get_db)):
    customers = db.query(Customer).order_by(Customer.name).all()
    return [c.to_dict() for c in customers]


@router.post("/")
def create_customer(payload: dict, db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Customer name is required")
    customer = Customer(
        name=name,
        name_tamil=(payload.get("name_tamil") or "").strip() or None,
        phone=(payload.get("phone") or "").strip() or None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer.to_dict()


@router.delete("/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    db.delete(customer)
    db.commit()
    return {"message": "Customer deleted"}

"""
Loan / Advance Account Models

LoanAccount  — one record per customer who has borrowed money
LoanTransaction — individual debit/credit entries on that account
  types:
    borrow   — money given to the farmer upfront
    repay    — money returned (cash or bill deduction)
    interest — monthly interest charge applied to outstanding balance
"""

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class LoanAccount(Base):
    __tablename__ = "loan_accounts"

    id                   = Column(Integer, primary_key=True, index=True)
    customer_id          = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)
    customer_name        = Column(String(200), nullable=False, index=True)
    customer_name_tamil  = Column(String(200), nullable=True)
    interest_rate        = Column(Float, nullable=False, default=2.0)   # % per month
    status               = Column(String(20), default="active")         # active / closed
    notes                = Column(Text, nullable=True)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self, balance: float = 0.0, total_borrowed: float = 0.0,
                total_repaid: float = 0.0, total_interest: float = 0.0):
        return {
            "id":                  self.id,
            "customer_id":         self.customer_id,
            "customer_name":       self.customer_name,
            "customer_name_tamil": self.customer_name_tamil,
            "interest_rate":       self.interest_rate,
            "status":              self.status,
            "notes":               self.notes,
            "created_at":          str(self.created_at),
            "balance":             round(balance, 2),
            "total_borrowed":      round(total_borrowed, 2),
            "total_repaid":        round(total_repaid, 2),
            "total_interest":      round(total_interest, 2),
        }


class LoanTransaction(Base):
    __tablename__ = "loan_transactions"

    id               = Column(Integer, primary_key=True, index=True)
    account_id       = Column(Integer, ForeignKey("loan_accounts.id"), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False)
    # borrow   → increases balance (money given to farmer)
    # repay    → decreases balance (cash or bill deduction)
    # interest → increases balance (monthly interest charge)

    amount           = Column(Float, nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    notes            = Column(Text, nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id":               self.id,
            "account_id":       self.account_id,
            "transaction_type": self.transaction_type,
            "amount":           round(self.amount, 2),
            "transaction_date": str(self.transaction_date),
            "notes":            self.notes,
            "created_at":       str(self.created_at),
        }

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String, nullable=False)        # English / transliterated
    name_tamil = Column(String, nullable=True)         # Tamil script
    phone      = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id":         self.id,
            "name":       self.name,
            "name_tamil": self.name_tamil,
            "phone":      self.phone,
            "created_at": str(self.created_at),
        }

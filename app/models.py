from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Index
from sqlalchemy.sql import func
from .database import Base

class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    address = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    creation_batch_id = Column(String, index=True, nullable=False)
    active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_batch_active', 'creation_batch_id', 'active'),
        Index('idx_name_active', 'name', 'active'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "phone": self.phone,
            "creation_batch_id": self.creation_batch_id,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

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


class BulkOperation(Base):
    __tablename__ = "bulk_operations"

    id = Column(String, primary_key=True)  # batch_id
    status = Column(String, nullable=False)  # 'in_progress', 'completed', 'failed', 'paused'
    total_rows = Column(Integer, nullable=False)
    processed_rows = Column(Integer, default=0)
    failed_rows = Column(Integer, default=0)
    current_row = Column(Integer, default=0)  # Last processed row number
    error_details = Column(Text, nullable=True)  # JSON string of errors
    file_content = Column(Text, nullable=True)  # Base64 encoded CSV content for resume
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_status', 'status'),
        Index('idx_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "total_rows": self.total_rows,
            "processed_rows": self.processed_rows,
            "failed_rows": self.failed_rows,
            "current_row": self.current_row,
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class HospitalBase(BaseModel):
    name: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    phone: Optional[str] = None

class HospitalCreate(HospitalBase):
    creation_batch_id: Optional[str] = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

class HospitalUpdate(HospitalBase):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None

class Hospital(HospitalBase):
    id: int
    creation_batch_id: Optional[str] = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

class BulkCreateResponse(BaseModel):
    batch_id: str
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    processing_time_seconds: float
    batch_activated: bool
    hospitals: List[dict]

class HospitalProcessingResult(BaseModel):
    row: int
    hospital_id: Optional[int] = None
    name: Optional[str] = None
    status: str
    error: Optional[str] = None
    data: Optional[str] = None


class BulkOperation(BaseModel):
    id: str
    status: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    current_row: int
    error_details: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResumeRequest(BaseModel):
    batch_id: str
    from_row: Optional[int] = None


class ResumeResponse(BaseModel):
    batch_id: str
    status: str
    resumed_from_row: int
    remaining_rows: int
    message: str


class PaginatedHospitalResponse(BaseModel):
    hospitals: List[Hospital]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

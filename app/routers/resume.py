import csv
import uuid
import time
import json
import base64
from io import StringIO
from typing import List, Optional
import os
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from .. import models, schemas, database

MAX_CSV_ROWS = int(os.getenv("MAX_CSV_ROWS", "20"))

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/bulk/operations/{batch_id}", response_model=schemas.BulkOperation)
def get_bulk_operation(batch_id: str, db: Session = Depends(get_db)):
    operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Bulk operation not found")
    return operation

@router.get("/bulk/operations", response_model=List[schemas.BulkOperation])
def get_bulk_operations(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(models.BulkOperation)
    if status:
        query = query.filter(models.BulkOperation.status == status)
    operations = query.order_by(models.BulkOperation.created_at.desc()).limit(limit).all()
    return operations

@router.post("/bulk/operations/{batch_id}/resume", response_model=schemas.ResumeResponse)
async def resume_bulk_operation(
    batch_id: str,
    resume_request: schemas.ResumeRequest,
    db: Session = Depends(get_db)
):
    # Get the bulk operation
    operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Bulk operation not found")
    
    if operation.status not in ["failed", "paused"]:
        raise HTTPException(status_code=400, detail=f"Cannot resume operation with status: {operation.status}")
    
    if not operation.file_content:
        raise HTTPException(status_code=400, detail="No file content available for resume")
    
    # Decode the stored file content
    try:
        decoded_content = base64.b64decode(operation.file_content).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to decode stored file content")
    
    # Determine resume row
    resume_row = resume_request.from_row if resume_request.from_row is not None else operation.current_row + 1
    
    if resume_row < 1 or resume_row > operation.total_rows:
        raise HTTPException(status_code=400, detail=f"Invalid resume row: {resume_row}")
    
    # Update operation status
    operation.status = "in_progress"
    operation.current_row = resume_row - 1
    db.commit()
    
    # Parse CSV and resume processing
    try:
        df = pd.read_csv(StringIO(decoded_content))
        hospitals_data = df.to_dict("records")
        has_headers = True
    except Exception:
        try:
            lines = decoded_content.strip().split("\n")
            first_line = lines[0]
            if any(c.isalpha() for c in first_line):
                csv_reader = csv.DictReader(StringIO(decoded_content))
                hospitals_data = list(csv_reader)
                has_headers = True
            else:
                csv_reader = csv.reader(StringIO(decoded_content))
                hospitals_data = []
                for row in csv_reader:
                    if len(row) >= 2:
                        hospitals_data.append({
                            "name": row[0].strip() if len(row) > 0 else "",
                            "address": row[1].strip() if len(row) > 1 else "",
                            "phone": row[2].strip() if len(row) > 2 else "",
                        })
                has_headers = False
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")
    
    # Resume processing from the specified row
    success_count = operation.processed_rows
    failed_count = operation.failed_rows
    errors = json.loads(operation.error_details or "[]")
    
    for idx in range(resume_row - 1, len(hospitals_data)):
        try:
            row = hospitals_data[idx]
            if has_headers:
                name = str(row.get("name") or row.get("Name", "")).strip()
                address = str(row.get("address") or row.get("Address", "")).strip()
                phone = (str(row.get("phone") or row.get("Phone", "")).strip() or None)
            else:
                name = str(row.get("name", "")).strip()
                address = str(row.get("address", "")).strip()
                phone = (str(row.get("phone", "")).strip() or None)

            # Skip completely empty rows
            if (not name and not address and not phone) or \
               (name.lower() in ['nan', 'none', ''] and 
                address.lower() in ['nan', 'none', ''] and 
                (phone is None or phone.lower() in ['nan', 'none', ''])):
                continue

            # Validate required fields
            if (not name or not address or 
                name.lower() in ['nan', 'none', ''] or 
                address.lower() in ['nan', 'none', '']):
                raise ValueError("Name and address are required")

            # Create hospital record
            hospital_obj = models.Hospital(
                name=name,
                address=address,
                phone=phone,
                creation_batch_id=batch_id,
                active=False,
            )
            db.add(hospital_obj)
            db.commit()
            
            success_count += 1
            operation.current_row = idx + 1
            operation.processed_rows = success_count
            
            # Update checkpoint every 10 records
            if (idx + 1) % 10 == 0:
                db.commit()
                
        except Exception as e:
            failed_count += 1
            operation.failed_rows = failed_count
            errors.append({
                "row": idx + 1,
                "error": str(e),
                "data": str(row)
            })
            operation.error_details = json.dumps(errors)
            db.commit()
    
    # Final update
    if failed_count == 0:
        operation.status = "completed"
        operation.completed_at = func.now()
        # Activate all hospitals in this batch
        db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).update({"active": True})
    else:
        operation.status = "failed"
    
    operation.error_details = json.dumps(errors)
    db.commit()
    
    return schemas.ResumeResponse(
        batch_id=batch_id,
        status=operation.status,
        resumed_from_row=resume_row,
        remaining_rows=operation.total_rows - resume_row + 1,
        message=f"Operation resumed from row {resume_row}. Status: {operation.status}"
    )

@router.post("/bulk/operations/{batch_id}/pause")
def pause_bulk_operation(batch_id: str, db: Session = Depends(get_db)):
    operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Bulk operation not found")
    
    if operation.status != "in_progress":
        raise HTTPException(status_code=400, detail=f"Cannot pause operation with status: {operation.status}")
    
    operation.status = "paused"
    db.commit()
    
    return {"message": "Operation paused successfully"}

@router.delete("/bulk/operations/{batch_id}")
def delete_bulk_operation(batch_id: str, db: Session = Depends(get_db)):
    operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Bulk operation not found")
    
    # Delete associated hospitals
    db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).delete()
    
    # Delete operation record
    db.delete(operation)
    db.commit()
    
    return {"message": "Operation and associated data deleted successfully"}

import csv
import uuid
import time
import json
import asyncio
from io import StringIO
from typing import List, Optional
import os
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
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

@router.post("/hospitals/bulk/big_file", response_model=schemas.BulkCreateResponse)
async def bulk_create_hospitals_realtime(
    file: UploadFile = File(...),
    sleep_duration: float = 0.5,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Bulk create hospitals with sleep for real-time status monitoring demonstration.
    Each hospital creation will be delayed by sleep_duration seconds.
    """
    start_time = time.time()
    
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    if sleep_duration < 0 or sleep_duration > 5:
        raise HTTPException(status_code=400, detail="Sleep duration must be between 0 and 5 seconds")

    contents = await file.read()
    if not contents or len(contents.strip()) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    try:
        decoded_content = contents.decode("utf-8")
        if not decoded_content.strip():
            raise HTTPException(status_code=400, detail="File contains only whitespace")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 encoded text")

    # Parse CSV
    try:
        df = pd.read_csv(StringIO(decoded_content))
        hospitals_data = df.to_dict("records")
        has_headers = True
    except Exception:
        try:
            content_str = decoded_content
            lines = content_str.strip().split("\n")
            first_line = lines[0]
            if any(c.isalpha() for c in first_line):
                csv_reader = csv.DictReader(StringIO(content_str))
                hospitals_data = list(csv_reader)
                has_headers = True
            else:
                csv_reader = csv.reader(StringIO(content_str))
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
            raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")

    if len(hospitals_data) > MAX_CSV_ROWS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_CSV_ROWS} hospitals allowed per CSV file")

    batch_id = str(uuid.uuid4())
    
    # Create bulk operation record for tracking
    bulk_operation = models.BulkOperation(
        id=batch_id,
        status="in_progress",
        total_rows=len(hospitals_data),
        processed_rows=0,
        failed_rows=0,
        current_row=0,
        error_details="[]",
        file_content=None  # Not storing for this demo
    )
    db.add(bulk_operation)
    db.commit()

    # Start background processing
    background_tasks.add_task(
        process_hospitals_with_sleep,
        hospitals_data,
        batch_id,
        sleep_duration,
        has_headers,
        db
    )

    return {
        "batch_id": batch_id,
        "total_hospitals": len(hospitals_data),
        "processed_hospitals": 0,
        "failed_hospitals": 0,
        "processing_time_seconds": 0,
        "batch_activated": False,
        "hospitals": [],
        "message": "Bulk operation started. Check status using the batch_id.",
        "sleep_duration": sleep_duration
    }

async def process_hospitals_with_sleep(
    hospitals_data: List[dict],
    batch_id: str,
    sleep_duration: float,
    has_headers: bool,
    db: Session
):
    """Background task to process hospitals with sleep delays - saves each record individually"""
    success_count = 0
    failed_count = 0
    errors = []
    processed_hospitals = []
    
    # Get a new database session for background task
    db = database.SessionLocal()
    
    try:
        for idx, row in enumerate(hospitals_data, start=1):
            try:
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

                # Create and save hospital record individually (like default bulk endpoint)
                hospital_obj = models.Hospital(
                    name=name,
                    address=address,
                    phone=phone,
                    creation_batch_id=batch_id,
                    active=False,
                )
                db.add(hospital_obj)
                db.commit()  # Save immediately after each record
                db.refresh(hospital_obj)  # Get the assigned ID
                
                success_count += 1
                processed_hospitals.append({
                    "row": idx,
                    "hospital_id": hospital_obj.id,
                    "name": name,
                    "status": "created"
                })
                
                # Sleep after each record save
                await asyncio.sleep(sleep_duration)
                
                # Update progress after each record (real-time monitoring)
                operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
                if operation:
                    operation.current_row = idx
                    operation.processed_rows = success_count
                    operation.error_details = json.dumps(errors)
                    db.commit()
                    
            except Exception as e:
                failed_count += 1
                errors.append({
                    "row": idx,
                    "error": str(e),
                    "data": str(row)
                })
                processed_hospitals.append({
                    "row": idx,
                    "error": str(e),
                    "data": str(row),
                    "status": "failed"
                })
                
                # Update error progress
                operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
                if operation:
                    operation.current_row = idx
                    operation.failed_rows = failed_count
                    operation.error_details = json.dumps(errors)
                    db.commit()

        # Final update
        operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
        if operation:
            operation.processed_rows = success_count
            operation.failed_rows = failed_count
            operation.error_details = json.dumps(errors)
            
            if failed_count == 0:
                operation.status = "completed"
                operation.completed_at = func.now()
                # Activate all hospitals in this batch
                db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).update({"active": True})
            else:
                operation.status = "failed"
            
            db.commit()
            
    finally:
        db.close()

@router.get("/hospitals/bulk/status/{batch_id}")
def get_bulk_operation_progress(batch_id: str, db: Session = Depends(get_db)):
    """Get comprehensive progress information for bulk operation"""
    operation = db.query(models.BulkOperation).filter(models.BulkOperation.id == batch_id).first()
    if not operation:
        raise HTTPException(status_code=404, detail="Bulk operation not found")
    
    # Calculate progress percentage
    progress_percentage = 0
    if operation.total_rows > 0:
        progress_percentage = round((operation.current_row / operation.total_rows) * 100, 2)
    
    # Get actual hospital count for this batch
    hospital_count = db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).count()
    
    return {
        "batch_id": batch_id,
        "status": operation.status,
        "total_rows": operation.total_rows,
        "current_row": operation.current_row,
        "processed_rows": operation.processed_rows,
        "failed_rows": operation.failed_rows,
        "progress_percentage": progress_percentage,
        "hospital_count": hospital_count,
        "errors": json.loads(operation.error_details or "[]"),
        "created_at": operation.created_at,
        "updated_at": operation.updated_at,
        "completed_at": operation.completed_at
    }

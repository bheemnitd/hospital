import csv
import uuid
import time
import httpx
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import models, schemas, database
from datetime import datetime
import pandas as pd
from io import StringIO

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MAX_CSV_SIZE_MB = int(os.getenv("MAX_CSV_SIZE_MB", "10"))
MAX_CSV_ROWS = int(os.getenv("MAX_CSV_ROWS", "20"))
BULK_PROCESSING_BATCH_SIZE = int(os.getenv("BULK_PROCESSING_BATCH_SIZE", "5"))
HTTP_TIMEOUT_CONNECT = int(os.getenv("HTTP_TIMEOUT_CONNECT", "10"))
HTTP_TIMEOUT_READ = int(os.getenv("HTTP_TIMEOUT_READ", "30"))
HTTP_TIMEOUT_WRITE = int(os.getenv("HTTP_TIMEOUT_WRITE", "30"))
HTTP_TIMEOUT_TOTAL = int(os.getenv("HTTP_TIMEOUT_TOTAL", "60"))

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/hospitals/", response_model=List[schemas.Hospital])
def get_all_hospitals(db: Session = Depends(get_db)):
    hospitals = db.query(models.Hospital).all()
    return hospitals

@router.post("/hospitals/", response_model=schemas.Hospital)
def create_hospital(hospital: schemas.HospitalCreate, db: Session = Depends(get_db)):
    db_hospital = models.Hospital(**hospital.dict())
    db.add(db_hospital)
    db.commit()
    db.refresh(db_hospital)
    return db_hospital

@router.get("/hospitals/{hospital_id}", response_model=schemas.Hospital)
def get_hospital_by_id(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital

@router.put("/hospitals/{hospital_id}", response_model=schemas.Hospital)
def update_hospital(hospital_id: int, hospital_update: schemas.HospitalUpdate, db: Session = Depends(get_db)):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    update_data = hospital_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hospital, field, value)
    
    db.commit()
    db.refresh(hospital)
    return hospital

@router.delete("/hospitals/{hospital_id}")
def delete_hospital(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    db.delete(hospital)
    db.commit()
    return

@router.get("/hospitals/batch/{batch_id}", response_model=List[schemas.Hospital])
def get_hospitals_by_batch_id(batch_id: str, db: Session = Depends(get_db)):
    hospitals = db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).all()
    if not hospitals:
        raise HTTPException(status_code=404, detail=f"No hospitals found for batch ID: {batch_id}")
    return hospitals

@router.patch("/hospitals/batch/{batch_id}/activate")
def activate_hospitals_by_batch(batch_id: str, db: Session = Depends(get_db)):
    result = (
        db.query(models.Hospital)
        .filter(models.Hospital.creation_batch_id == batch_id)
        .update({"active": True})
    )
    if result == 0:
        raise HTTPException(status_code=404, detail="No hospitals found for batch ID")

    db.commit()
    
    return "successfully activated"

@router.delete("/hospitals/batch/{batch_id}")
def delete_hospitals_by_batch(batch_id: str, db: Session = Depends(get_db)):
    hospitals = db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).all()
    if not hospitals:
        raise HTTPException(status_code=404, detail="No hospitals found for batch ID")
    
    db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).delete()
    db.commit()
    return "Deleted Successfully"

@router.post("/hospitals/bulk", response_model=schemas.BulkCreateResponse)
async def bulk_create_hospitals(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    start_time = time.time()
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    contents = await file.read()
    if not contents or len(contents.strip()) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    try:
        decoded_content = contents.decode('utf-8')
        if not decoded_content.strip():
            raise HTTPException(status_code=400, detail="File contains only whitespace")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 encoded text")
    
    try:
        df = pd.read_csv(StringIO(decoded_content))
        hospitals_data = df.to_dict('records')
        has_headers = True
        
        # Check if required columns exist
        required_columns = ['name', 'address']
        available_columns = [col.lower().strip() for col in df.columns]
        
        missing_columns = []
        for req_col in required_columns:
            if req_col not in available_columns:
                # Check for case-insensitive matches
                found = False
                for avail_col in available_columns:
                    if req_col.lower() == avail_col.lower() or req_col.title() == avail_col.title():
                        found = True
                        break
                if not found:
                    missing_columns.append(req_col)
        
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {', '.join(missing_columns)}. Available columns: {', '.join(df.columns.tolist())}"
            )
            
    except Exception as e:
        if "Missing required columns" in str(e):
            raise e
        try:
            content_str = decoded_content
            lines = content_str.strip().split('\n')

            if len(lines) == 0:
                raise HTTPException(status_code=400, detail="CSV file is empty")
            
            if len(lines) == 1:
                raise HTTPException(status_code=400, detail="CSV file must have at least one data row")

            first_line = lines[0]
            if any(c.isalpha() for c in first_line):
                csv_reader = csv.DictReader(StringIO(content_str))
                hospitals_data = list(csv_reader)
                has_headers = True
                
                # Check if required fields exist in header
                if hospitals_data:
                    sample_row = hospitals_data[0]
                    required_fields = ['name', 'address']
                    missing_fields = []
                    
                    for field in required_fields:
                        field_found = False
                        for key in sample_row.keys():
                            if key.lower().strip() == field.lower().strip():
                                field_found = True
                                break
                        if not field_found:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Missing required fields in CSV header: {', '.join(missing_fields)}. Available fields: {', '.join(sample_row.keys())}"
                        )
            else:
                csv_reader = csv.reader(StringIO(content_str))
                hospitals_data = []
                for row in csv_reader:
                    if len(row) >= 2:
                        hospitals_data.append({
                            'name': row[0].strip() if len(row) > 0 else '',
                            'address': row[1].strip() if len(row) > 1 else '',
                            'phone': row[2].strip() if len(row) > 2 else ''
                        })
                    else:
                        raise HTTPException(status_code=400, detail=f"Row {len(hospitals_data) + 1}: At least 2 columns required (name, address)")
                has_headers = False
        except Exception as e:
            if "Missing required fields" in str(e) or "At least 2 columns required" in str(e):
                raise e
            raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
    
    if len(hospitals_data) > MAX_CSV_ROWS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_CSV_ROWS} hospitals allowed per CSV file")
    
    batch_id = str(uuid.uuid4())
    
    processed_hospitals = []
    success_count = 0
    failed_count = 0
    actual_total_count = 0

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            HTTP_TIMEOUT_TOTAL,
            connect=HTTP_TIMEOUT_CONNECT,
            read=HTTP_TIMEOUT_READ,
            write=HTTP_TIMEOUT_WRITE
        )
    ) as client:
        for idx, row in enumerate(hospitals_data, start=1):
            try:
                if has_headers:
                    name = str(row.get('name') or row.get('Name', '')).strip()
                    address = str(row.get('address') or row.get('Address', '')).strip()
                    phone = (str(row.get('phone') or row.get('Phone', '')).strip() or None)
                else:
                    name = str(row.get('name', '')).strip()
                    address = str(row.get('address', '')).strip()
                    phone = (str(row.get('phone', '')).strip() or None)

                # Skip completely empty rows (all fields missing/empty)
                if (not name and not address and not phone) or \
                   (name.lower() in ['nan', 'none', ''] and 
                    address.lower() in ['nan', 'none', ''] and 
                    (phone is None or phone.lower() in ['nan', 'none', ''])):
                    continue

                actual_total_count += 1

                # Validate required fields (name and address must be present)
                if (not name or not address or 
                    name.lower() in ['nan', 'none', ''] or 
                    address.lower() in ['nan', 'none', '']):
                    raise ValueError("Name and address are required")
                
                hospital_data = {
                    "name": name,
                    "address": address,
                    "phone": phone,
                    "creation_batch_id": batch_id
                }

                response = await client.post(f"{BASE_URL}/hospitals/", json=hospital_data)

                if response.status_code == 200:
                    created = response.json()
                    processed_hospitals.append({
                        "row": idx,
                        "hospital_id": created["id"],
                        "name": created["name"],
                        "status": "created_and_updated"
                    })
                    success_count += 1
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")

            except Exception as e:
                failed_count += 1
                processed_hospitals.append({
                    "row": idx,
                    "error": str(e),
                    "data": str(row),
                    "status": "failed"
                })

        batch_activated = False
        activate_error: Optional[str] = None

        if success_count > 0 and failed_count == 0:
            try:
                patch_resp = await client.patch(f"{BASE_URL}/hospitals/batch/{batch_id}/activate")
                if patch_resp.status_code == 200:
                    batch_activated = True
                else:
                    batch_activated = False
            except Exception as e:
                batch_activated = False

    processing_time = time.time() - start_time

    result = {
        "batch_id": batch_id,
        "total_hospitals": actual_total_count,
        "processed_hospitals": success_count,
        "failed_hospitals": failed_count,
        "processing_time_seconds": round(processing_time, 2),
        "batch_activated": batch_activated,
        "hospitals": processed_hospitals
    }

    return result

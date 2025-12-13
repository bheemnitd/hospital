import csv
import uuid
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import models, schemas, database
from datetime import datetime
import pandas as pd
from io import StringIO

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
    hospitals = db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).all()
    if not hospitals:
        raise HTTPException(status_code=404, detail="No hospitals found for batch ID")
    
    db.query(models.Hospital).filter(models.Hospital.creation_batch_id == batch_id).update({"active": True})
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
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    # Read and parse the CSV file
    contents = await file.read()
    try:
        # Try reading with pandas first (more robust CSV handling)
        df = pd.read_csv(StringIO(contents.decode('utf-8')))
        # Convert to list of dicts
        hospitals_data = df.to_dict('records')
        has_headers = True
    except Exception:
        # Fallback to csv module if pandas fails
        try:
            content_str = contents.decode('utf-8')
            lines = content_str.strip().split('\n')

            if len(lines) > 0:
                first_line = lines[0]
                if any(c.isalpha() for c in first_line):
                    # Has headers
                    csv_reader = csv.DictReader(StringIO(content_str))
                    hospitals_data = list(csv_reader)
                    has_headers = True
                else:
                    # No headers - use positional indexing
                    csv_reader = csv.reader(StringIO(content_str))
                    hospitals_data = []
                    for row in csv_reader:
                        if len(row) >= 2:  # At least name and address
                            hospitals_data.append({
                                'name': row[0].strip() if len(row) > 0 else '',
                                'address': row[1].strip() if len(row) > 1 else '',
                                'phone': row[2].strip() if len(row) > 2 else ''
                            })
                    has_headers = False
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
    
    # Validate maximum CSV size constraint
    if len(hospitals_data) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 hospitals allowed per CSV file")
    
    # Generate a unique batch ID
    batch_id = str(uuid.uuid4())
    
    processed_hospitals = []
    success_count = 0
    failed_count = 0

    base_url = "http://localhost:8000"  # adjust if needed

    # Use async HTTP client to avoid blocking
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0, read=30.0, write=30.0)) as client:
        for idx, row in enumerate(hospitals_data, start=1):
            try:
                # Build hospital data (keep them INACTIVE initially)
                if has_headers:
                    hospital_data = {
                        "name": str(row.get('name') or row.get('Name', '')).strip(),
                        "address": str(row.get('address') or row.get('Address', '')).strip(),
                        "phone": (str(row.get('phone') or row.get('Phone', '')).strip() or None),
                        "creation_batch_id": batch_id,
                    }
                else:
                    hospital_data = {
                        "name": str(row.get('name', '')).strip(),
                        "address": str(row.get('address', '')).strip(),
                        "phone": (str(row.get('phone', '')).strip() or None),
                        "creation_batch_id": batch_id,
                    }

                # Validate required fields
                if not hospital_data["name"] or not hospital_data["address"]:
                    raise ValueError("Name and address are required")
                
                print("hospital_data:", hospital_data)

                # POST /hospitals/
                response = await client.post(f"{base_url}/hospitals/", json=hospital_data)

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

        # Condition 4: activate via PATCH only if requested and all succeeded
        batch_activated = False
        activate_error: Optional[str] = None

        if success_count > 0 and failed_count == 0:
            try:
                patch_resp = await client.patch(f"{base_url}/hospitals/batch/{batch_id}/activate")
                if patch_resp.status_code == 200:
                    batch_activated = True
                else:
                    batch_activated = False
            except Exception as e:
                batch_activated = False

    processing_time = time.time() - start_time

    # Condition 5: comprehensive, accurate summary
    result = {
        "batch_id": batch_id,
        "total_hospitals": len(hospitals_data),
        "processed_hospitals": success_count,
        "failed_hospitals": failed_count,
        "processing_time_seconds": round(processing_time, 2),
        "batch_activated": batch_activated,
        "hospitals": processed_hospitals
    }

    return result

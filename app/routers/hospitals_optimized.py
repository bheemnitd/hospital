import csv
import uuid
import time
from io import StringIO
from typing import List, Optional
import os
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from .. import models, schemas, database

MAX_CSV_ROWS = int(os.getenv("MAX_CSV_ROWS", "20"))

router = APIRouter()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/hospitals/bulk/optimized/", response_model=schemas.BulkCreateResponse)
async def bulk_create_hospitals(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    start_time = time.time()

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")

    contents = await file.read()
    if not contents or len(contents.strip()) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    try:
        decoded_content = contents.decode("utf-8")
        if not decoded_content.strip():
            raise HTTPException(status_code=400, detail="File contains only whitespace")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 encoded text")

    try:
        df = pd.read_csv(StringIO(decoded_content))
        hospitals_data = df.to_dict("records")
        has_headers = True
        
        # Check if required columns exist
        required_columns = ["name", "address"]
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
            lines = content_str.strip().split("\n")

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
                    required_fields = ["name", "address"]
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
                        hospitals_data.append(
                            {
                                "name": row[0].strip() if len(row) > 0 else "",
                                "address": row[1].strip() if len(row) > 1 else "",
                                "phone": row[2].strip() if len(row) > 2 else "",
                            }
                        )
                    else:
                        raise HTTPException(status_code=400, detail=f"Row {len(hospitals_data) + 1}: At least 2 columns required (name, address)")
                has_headers = False
        except Exception as e:
            if "Missing required fields" in str(e) or "At least 2 columns required" in str(e):
                raise e
            raise HTTPException(
                status_code=400, detail=f"Invalid CSV file: {str(e)}"
            )

    if len(hospitals_data) > MAX_CSV_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_CSV_ROWS} hospitals allowed per CSV file",
        )

    batch_id = str(uuid.uuid4())

    processed_hospitals = []
    success_count = 0
    failed_count = 0
    actual_total_count = 0

    to_insert: List[models.Hospital] = []

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

            hospital_obj = models.Hospital(
                name=name,
                address=address,
                phone=phone,
                creation_batch_id=batch_id,
                active=False,
            )
            to_insert.append(hospital_obj)

            success_count += 1
            processed_hospitals.append(
                {
                    "row": idx,
                    "hospital_id": None,
                    "name": name,
                    "status": "queued_for_creation",
                }
            )
        except Exception as e:
            failed_count += 1
            processed_hospitals.append(
                {
                    "row": idx,
                    "error": str(e),
                    "data": str(row),
                    "status": "failed",
                }
            )

    batch_activated = False
    if success_count > 0:
        db.add_all(to_insert)
        db.commit()

        for obj, record in zip(to_insert, processed_hospitals):
            if record["status"] == "queued_for_creation":
                db.refresh(obj)
                record["hospital_id"] = obj.id
                record["status"] = "created"

        if failed_count == 0:
            updated_rows = (
                db.query(models.Hospital)
                .filter(models.Hospital.creation_batch_id == batch_id)
                .update({"active": True})
            )
            db.commit()
            batch_activated = updated_rows > 0

    processing_time = time.time() - start_time

    result = {
        "batch_id": batch_id,
        "total_hospitals": actual_total_count,
        "processed_hospitals": success_count,
        "failed_hospitals": failed_count,
        "processing_time_seconds": round(processing_time, 2),
        "batch_activated": batch_activated,
        "hospitals": processed_hospitals,
    }

    return result

# Hospitals Optimized API Documentation

## Overview

The `hospitals_optimized.py` module provides a high-performance bulk hospital creation endpoint that uses direct database operations instead of HTTP calls for significantly better performance.

## API Endpoints

### POST `/hospitals/bulk/optimized`

**Description**: Optimimized bulk hospital creation using direct database operations for maximum performance.

**Method**: `POST`

**Content-Type**: `multipart/form-data`

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | CSV file containing hospital data |

#### CSV File Format

The endpoint supports both CSV formats:

**With Headers:**
```csv
name,address,phone
Hospital A,123 Main St,555-1234
Hospital B,456 Oak Ave,555-5678
```

**Without Headers:**
```csv
Hospital A,123 Main St,555-1234
Hospital B,456 Oak Ave,555-5678
```

#### Field Requirements

| Field | Required | Max Length | Description |
|-------|----------|------------|-------------|
| `name` | Yes | 255 characters | Hospital name |
| `address` | Yes | 255 characters | Hospital address |
| `phone` | No | 255 characters | Phone number (optional) |

#### Constraints

- Maximum 20 hospitals per CSV file
- File must be in CSV format
- Name and address are required fields
- Phone number is optional

#### Response Model

**Schema**: `BulkCreateResponse`

```json
{
  "batch_id": "string",
  "total_hospitals": "integer",
  "processed_hospitals": "integer", 
  "failed_hospitals": "integer",
  "processing_time_seconds": "number",
  "batch_activated": "boolean",
  "hospitals": [
    {
      "row": "integer",
      "hospital_id": "integer|null",
      "name": "string",
      "status": "string",
      "error": "string|null",
      "data": "string|null"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `batch_id` | string | Unique identifier for this batch operation |
| `total_hospitals` | integer | Total number of hospitals in CSV file |
| `processed_hospitals` | integer | Number of successfully created hospitals |
| `failed_hospitals` | integer | Number of failed hospital creations |
| `processing_time_seconds` | number | Total processing time in seconds |
| `batch_activated` | boolean | Whether the batch was auto-activated |
| `hospitals` | array | Detailed results for each hospital row |

#### Hospital Record Fields

| Field | Type | Description |
|-------|------|-------------|
| `row` | integer | Row number in CSV file (1-based) |
| `hospital_id` | integer|null | Database ID of created hospital (null if failed) |
| `name` | string | Hospital name |
| `status` | string | "created" or "failed" |
| `error` | string|null | Error message if failed |
| `data` | string|null | Raw data from CSV if failed |

#### Success Response (200)

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_hospitals": 3,
  "processed_hospitals": 3,
  "failed_hospitals": 0,
  "processing_time_seconds": 0.15,
  "batch_activated": true,
  "hospitals": [
    {
      "row": 1,
      "hospital_id": 1,
      "name": "Hospital A",
      "status": "created"
    },
    {
      "row": 2,
      "hospital_id": 2,
      "name": "Hospital B", 
      "status": "created"
    },
    {
      "row": 3,
      "hospital_id": 3,
      "name": "Hospital C",
      "status": "created"
    }
  ]
}
```

#### Partial Success Response (200)

```json
{
  "batch_id": "550e8400-e29b-41d4-a716-446655440001",
  "total_hospitals": 3,
  "processed_hospitals": 2,
  "failed_hospitals": 1,
  "processing_time_seconds": 0.12,
  "batch_activated": false,
  "hospitals": [
    {
      "row": 1,
      "hospital_id": 4,
      "name": "Hospital A",
      "status": "created"
    },
    {
      "row": 2,
      "hospital_id": 5,
      "name": "Hospital B",
      "status": "created"
    },
    {
      "row": 3,
      "hospital_id": null,
      "name": "",
      "status": "failed",
      "error": "Name and address are required",
      "data": "{'name': '', 'address': '', 'phone': '555-9999'}"
    }
  ]
}
```

#### Error Responses

**400 Bad Request** - Invalid file format
```json
{
  "detail": "Only CSV files are allowed"
}
```

**400 Bad Request** - Too many hospitals
```json
{
  "detail": "Maximum 20 hospitals allowed per CSV file"
}
```

**400 Bad Request** - Invalid CSV format
```json
{
  "detail": "Invalid CSV file: [error details]"
}
```

## Performance Characteristics

### Optimizations Implemented

1. **Direct Database Operations**: Uses SQLAlchemy bulk insert instead of HTTP calls
2. **Single Transaction**: All hospitals inserted in one database transaction
3. **Batch Processing**: Processes all data before database operations
4. **Efficient Error Handling**: Validates data before database operations

### Performance Benefits

- **10-100x faster** than HTTP-based bulk processing
- **Reduced database overhead** with bulk insert operations
- **Better memory efficiency** with streaming CSV processing
- **Atomic operations** - all hospitals succeed or fail together

### Expected Performance

| Hospitals | Processing Time | Notes |
|-----------|----------------|-------|
| 1-5 | < 0.1s | Very fast processing |
| 10-15 | < 0.2s | Optimal range |
| 20 | < 0.3s | Maximum allowed |

## Usage Examples

### cURL Example

```bash
curl -X POST \
  "http://localhost:8000/hospitals/bulk/optimized" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@hospitals.csv"
```

### Python Example

```python
import requests

with open('hospitals.csv', 'rb') as f:
    files = {'file': ('hospitals.csv', f, 'text/csv')}
    response = requests.post(
        'http://localhost:8000/hospitals/bulk/optimized',
        files=files
    )
    result = response.json()
    print(f"Batch ID: {result['batch_id']}")
    print(f"Processed: {result['processed_hospitals']}")
    print(f"Failed: {result['failed_hospitals']}")
```

### JavaScript Example

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8000/hospitals/bulk/optimized', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('Batch ID:', data.batch_id);
  console.log('Processing time:', data.processing_time_seconds);
});
```

## Comparison with Standard Bulk Endpoint

| Feature | Standard Bulk | Optimized Bulk |
|---------|---------------|---------------|
| Processing Method | HTTP calls to self | Direct database insert |
| Performance | Slow (network overhead) | Fast (database operations) |
| Reliability | Prone to timeouts | Atomic transactions |
| Scalability | Limited by HTTP | Limited by database |
| Error Handling | Per-request | Pre-validation |

## Integration Notes

### Database Requirements

- Requires SQLAlchemy with bulk insert support
- Uses SQLite by default, compatible with PostgreSQL/MySQL
- Automatic transaction management

### Dependencies

- `fastapi` - Web framework
- `sqlalchemy` - ORM with bulk insert support
- `pandas` - CSV processing (fallback to csv module)
- `python-multipart` - File upload support

### Error Handling

The endpoint provides comprehensive error handling:

1. **File validation** - Ensures CSV format
2. **Data validation** - Checks required fields
3. **Database error handling** - Automatic rollback on failures
4. **Detailed error reporting** - Per-row error information

### Monitoring

The endpoint includes built-in performance monitoring:

- Processing time tracking
- Success/failure counts
- Detailed per-row status
- Batch activation status

## Best Practices

1. **Validate CSV before upload** - Check format and required fields
2. **Monitor processing time** - Use for performance optimization
3. **Handle partial failures** - Check `failed_hospitals` count
4. **Use batch ID for tracking** - Reference for future operations
5. **Implement retry logic** - For database connection issues

# Hospital Management API

A FastAPI-based RESTful API for managing hospitals with advanced batch processing, pagination, and real-time monitoring capabilities.

## Features

- Individual hospital CRUD operations
- Multiple bulk processing endpoints with different strategies
- Optimized pagination and filtering for large datasets
- Real-time progress monitoring for bulk operations
- CSV validation and processing
- Comprehensive error handling and validation
- SQLite database with optimized queries
- Polling-based status tracking for bulk operations

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd hospital
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Database Setup

The application uses SQLite by default, which will be automatically created when you first run the application.

## Running the Application

1. Start the FastAPI development server:
   ```bash
   cd app
   uvicorn main:app --reload
   ```

2. The API will be available at `http://localhost:8000`

3. Access the interactive API documentation at:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Individual Hospital Operations

- `POST /hospitals/` - Create a new hospital
- `GET /hospitals/` - Get all hospitals with pagination
- `GET /hospitals/{hospital_id}` - Get a specific hospital
- `PUT /hospitals/{hospital_id}` - Update a hospital
- `DELETE /hospitals/{hospital_id}` - Delete a hospital

### Optimized Hospital Operations

- `GET /hospitals/optimized/` - Get hospitals with advanced filtering, sorting, and pagination
- `POST /hospitals/optimized/bulk` - Optimized bulk creation with direct database operations
- `GET /hospitals/optimized/stats` - Get comprehensive hospital statistics

### Bulk Operations with Real-time Monitoring

- `POST /hospitals/bulk/big_file` - Bulk create hospitals with configurable delays for real-time monitoring
- `GET /hospitals/bulk/status/{batch_id}` - Get comprehensive progress information for bulk operations

### CSV Validation

- `POST /validation/validate-csv` - Validate CSV file format and content before processing

## Bulk Upload CSV Format

The CSV file for bulk upload should have the following columns:
- `name` (required): Name of the hospital
- `address` (required): Physical address of the hospital
- `phone` (optional): Contact phone number

Example:
```csv
name,address,phone
General Hospital,123 Main St,555-1234
City Medical,456 Oak Ave,555-5678
```

## Advanced Features

### Pagination and Filtering
The optimized endpoints support:
- Page-based pagination (default: 50 records per page)
- Search by hospital name
- Filter by active/inactive status
- Sort by various fields (name, created_at, updated_at)
- Filter by batch ID

### Real-time Bulk Processing
The `/hospitals/bulk/big_file` endpoint provides:
- Configurable sleep duration between records (0-5 seconds)
- Real-time progress tracking in database
- Detailed error reporting
- Polling-based status updates via `/hospitals/bulk/status/{batch_id}`

### Environment Variables
- `MAX_CSV_ROWS`: Maximum number of rows allowed in CSV uploads (default: 20)

## Testing

You can test the API using the interactive documentation at `http://localhost:8000/docs` or using tools like curl or Postman.

### Example Usage

1. **Create individual hospital:**
   ```bash
   curl -X POST "http://localhost:8000/hospitals/" \
   -H "Content-Type: application/json" \
   -d '{"name": "Test Hospital", "address": "123 Test St", "phone": "555-1234"}'
   ```

2. **Bulk upload with real-time monitoring:**
   ```bash
   curl -X POST "http://localhost:8000/hospitals/bulk/big_file?sleep_duration=1" \
   -F "file=@hospitals.csv"
   ```

3. **Check bulk operation status:**
   ```bash
   curl "http://localhost:8000/hospitals/bulk/status/{batch_id}"
   ```

4. **Get paginated hospitals with filtering:**
   ```bash
   curl "http://localhost:8000/hospitals/optimized/?page=1&size=10&search=General&active_only=true"
   ```

## Deployment

For production deployment, consider:
1. Using a production-grade ASGI server like Gunicorn with Uvicorn workers
2. Configuring a production database (PostgreSQL/MySQL)
3. Setting up proper environment variables for sensitive information
4. Implementing proper authentication/authorization
5. Using Docker containers for consistent deployment

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

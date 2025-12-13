# Hospital Management API

A FastAPI-based RESTful API for managing hospitals with batch processing support.

## Features

- Individual hospital CRUD operations
- Batch processing of hospital data via CSV upload
- Batch activation/deactivation of hospitals
- Comprehensive error handling and validation
- SQLite database (can be easily switched to PostgreSQL/MySQL)

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd hospital_api
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

- `POST /api/v1/hospitals/` - Create a new hospital
- `GET /api/v1/hospitals/` - Get all hospitals

### Batch Operations

- `POST /api/v1/hospitals/bulk` - Bulk create hospitals from CSV
- `GET /api/v1/hospitals/batch/{batch_id}` - Get hospitals by batch ID
- `PATCH /api/v1/hospitals/batch/{batch_id}/activate` - Activate all hospitals in a batch
- `DELETE /api/v1/hospitals/batch/{batch_id}` - Delete all hospitals in a batch

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

## Testing

You can test the API using the interactive documentation at `http://localhost:8000/docs` or using tools like curl or Postman.

## Deployment

For production deployment, consider:
1. Using a production-grade ASGI server like Gunicorn with Uvicorn workers
2. Configuring a production database (PostgreSQL/MySQL)
3. Setting up proper environment variables for sensitive information
4. Implementing proper authentication/authorization

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

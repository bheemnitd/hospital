from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from . import models, schemas
from .database import engine, get_db
from .routers import hospitals
from .routers import hospitals_optimized
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Hospital Directory API",
    description="A RESTful API for managing hospital directory information with batch processing capabilities.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def health_check():
    return {"status": "ok"}

app.include_router(hospitals.router, prefix="")

app.include_router(hospitals_optimized.router, prefix="", tags=["Optimized Hospitals Directory"])
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.core.database import get_db
from src.core.config import settings

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "unhealthy"
    try:
        # Validate connection to the database
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": db_status
    }

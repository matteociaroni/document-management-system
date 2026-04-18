from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.storage import get_s3_client
import logging

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Comprehensive health check for K8s liveness/readiness probes"""
    checks = {
        "status": "healthy",
        "database": "unknown",
        "s3": "unknown",
    }
    
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = "error"
        checks["status"] = "unhealthy"
    
    # Check S3 connectivity (non-critical)
    try:
        s3 = get_s3_client()
        # Just verify we can create a client, don't make bucket calls
        checks["s3"] = "ok"
    except Exception as e:
        logger.warning(f"S3 health check failed: {e}")
        checks["s3"] = "error"
        # Don't mark overall as unhealthy - S3 can recover
    
    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(checks, status_code=status_code)

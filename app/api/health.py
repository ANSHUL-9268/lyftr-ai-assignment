"""
Health check endpoints for liveness and readiness probes.
"""
from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.core.database import check_db_connection
from app.core.logging import get_logger
from app.schemas.message import HealthResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Always returns 200 to indicate the service is alive."
)
async def liveness() -> HealthResponse:
    """
    Liveness probe - always returns 200.
    
    Used by orchestrators to check if the service is running.
    """
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Returns 200 if the service is ready to handle traffic."
)
async def readiness(response: Response) -> HealthResponse:
    """
    Readiness probe - checks if the service can handle traffic.
    
    Checks:
    - SQLite database is reachable and schema is applied
    - WEBHOOK_SECRET environment variable is configured
    """
    settings = get_settings()
    checks = {}
    is_ready = True
    
    # Check database connection
    db_ok = check_db_connection()
    checks["database"] = "ok" if db_ok else "failed"
    if not db_ok:
        is_ready = False
        logger.warning("Readiness check failed: database not reachable")
    
    # Check webhook secret is configured
    secret_ok = settings.is_webhook_secret_configured
    checks["webhook_secret"] = "ok" if secret_ok else "not configured"
    if not secret_ok:
        is_ready = False
        logger.warning("Readiness check failed: WEBHOOK_SECRET not configured")
    
    if is_ready:
        return HealthResponse(status="ok", checks=checks)
    else:
        response.status_code = 503
        return HealthResponse(status="not ready", checks=checks)

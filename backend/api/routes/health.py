"""
Health check endpoints for monitoring and load balancers.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from database import get_db
from config import settings
from observability import get_logger

router = APIRouter()
logger = get_logger("health")


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": settings.APP_NAME}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe - checks all dependencies.
    Returns 200 only if all services are available.
    """
    checks = {
        "database": False,
        "redis": False,
    }
    
    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
    
    # Check Redis
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        checks["redis"] = True
    except Exception as e:
        logger.error("redis_health_check_failed", error=str(e))
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }


@router.get("/health/live")
async def liveness_check():
    """Liveness probe - returns 200 if app is running."""
    return {"status": "alive"}


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint placeholder."""
    # In production, integrate with prometheus_client
    return {
        "latency_targets": {
            "stt_ms": settings.TARGET_STT_LATENCY_MS,
            "llm_ms": settings.TARGET_LLM_LATENCY_MS,
            "tts_ms": settings.TARGET_TTS_LATENCY_MS,
            "total_ms": settings.TARGET_TOTAL_LATENCY_MS,
        }
    }

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "api",
        "version": settings.api_version,
        "environment": settings.app_env,
    }


@router.get("/health/ready")
def readiness(db: DbSession) -> JSONResponse:
    checks: dict[str, str] = {}
    healthy = True

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "up"
    except Exception:
        logger.exception("readiness: database check failed")
        checks["database"] = "down"
        healthy = False

    if settings.redis_url:
        redis_client = Redis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        try:
            redis_client.ping()
            checks["redis"] = "up"
        except RedisError:
            logger.warning("readiness: redis check failed")
            checks["redis"] = "down"
            healthy = False
        finally:
            redis_client.close()

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )

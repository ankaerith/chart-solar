from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from backend.database import SessionLocal
from backend.workers.queue import get_redis

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict[str, Any]:
    db_ok = False
    redis_ok = False
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    try:
        get_redis().ping()
        redis_ok = True
    except Exception:
        pass
    healthy = db_ok and redis_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }

from fastapi import APIRouter
from sqlalchemy import text

from backend.database import SessionLocal
from backend.workers.queue import get_redis

router = APIRouter()


@router.get("/health")
async def health() -> dict:
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
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }

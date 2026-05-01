from typing import Any

from fastapi import APIRouter, Response, status

from backend.services.health_service import database_ok, queue_ok

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict[str, Any]:
    db_ok = await database_ok()
    redis_ok = queue_ok()
    healthy = db_ok and redis_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "db": db_ok,
        "redis": redis_ok,
    }

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/irradiance")
async def irradiance_tmy(lat: float, lon: float, source: str = "auto") -> dict[str, Any]:
    """Stub. Phase 1a returns 8760-hour TMY routed to NSRDB / PVGIS / Open-Meteo."""
    return {
        "lat": lat,
        "lon": lon,
        "source": source,
        "status": "not_implemented",
    }

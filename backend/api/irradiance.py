from typing import Annotated, Any

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/irradiance")
async def irradiance_tmy(
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
    source: str = "auto",
) -> dict[str, Any]:
    """Stub. Phase 1a returns 8760-hour TMY routed to NSRDB / PVGIS / Open-Meteo.

    Lat/lon bounds mirror engine.inputs.SystemInputs so the IO boundary
    rejects out-of-range coords before any provider is wired up.
    """
    return {
        "lat": lat,
        "lon": lon,
        "source": source,
        "status": "not_implemented",
    }

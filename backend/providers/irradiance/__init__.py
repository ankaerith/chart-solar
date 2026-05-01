"""IrradianceProvider port + auto-router.

Adapters live in subpackage modules (`nsrdb.py`, `pvgis.py`,
`openmeteo.py`); the engine talks to the `IrradianceProvider` Protocol
so a swap is one DI binding away. `pick_provider` routes by lat/lon:

* US                → NSRDB (NREL PSM3, free with API key)
* UK / Europe       → PVGIS (free, no key)
* anywhere else     → Open-Meteo (free fallback; paid Standard tier
                       behind `OPENMETEO_PAID_ENABLED`)

The router never returns `None`: Open-Meteo is the global fallback.

The shared TMY shape (``TmyData``, ``HOURS_PER_TMY``, ``IrradianceSource``,
``tmy_hour_calendar``, ``tmy_datetime_index``) lives in
``backend.domain.tmy``. They're re-exported here for backward
compatibility with non-engine callers; new code should import from
``backend.domain.tmy`` directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.config import Settings
from backend.config import settings as _global_settings
from backend.domain.tmy import (
    HOURS_PER_TMY,
    TMY_ANCHOR_YEAR,
    IrradianceSource,
    TmyData,
    tmy_datetime_index,
    tmy_hour_calendar,
)


@runtime_checkable
class IrradianceProvider(Protocol):
    """Fetch one location's 8760-hour TMY."""

    name: IrradianceSource

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData: ...


def _is_us(lat: float, lon: float) -> bool:
    """Cover the contiguous 48 + Alaska + Hawaii bounding boxes.

    Bounding-box approach is intentionally coarse — NSRDB itself rejects
    out-of-coverage points; we only use this to decide *which* provider
    to try first."""
    if 24.0 <= lat <= 49.5 and -125.0 <= lon <= -66.5:  # CONUS
        return True
    if 51.0 <= lat <= 71.5 and -179.5 <= lon <= -129.0:  # Alaska
        return True
    return 18.5 <= lat <= 22.5 and -161.0 <= lon <= -154.5  # Hawaii


def _is_uk_or_eu(lat: float, lon: float) -> bool:
    """PVGIS coverage box (Europe + Africa coast). Per JRC's published
    PVGIS-SARAH2 / PVGIS-NSRDB / PVGIS-ERA5 coverage map: lat 25..72,
    lon -25..40 is comfortably inside."""
    return 25.0 <= lat <= 72.0 and -25.0 <= lon <= 40.0


def pick_provider(
    lat: float,
    lon: float,
    *,
    settings: Settings | None = None,
) -> IrradianceProvider:
    """Auto-route to the best provider for this lat/lon.

    Imports adapters lazily to keep the Protocol module decoupled from
    concrete dependencies (httpx, etc.) — useful for documentation and
    fast import in pure tests."""
    cfg = settings or _global_settings

    if _is_us(lat, lon):
        from backend.providers.irradiance.nsrdb import NsrdbProvider

        return NsrdbProvider(
            api_key=cfg.nsrdb_api_key,
            user_email=cfg.nsrdb_user_email,
        )
    if _is_uk_or_eu(lat, lon):
        from backend.providers.irradiance.pvgis import PvgisProvider

        return PvgisProvider()
    from backend.providers.irradiance.openmeteo import OpenMeteoProvider

    return OpenMeteoProvider(
        paid_enabled=cfg.openmeteo_paid_enabled,
        api_key=cfg.openmeteo_paid_api_key,
    )


__all__ = [
    "HOURS_PER_TMY",
    "IrradianceProvider",
    "IrradianceSource",
    "TMY_ANCHOR_YEAR",
    "TmyData",
    "pick_provider",
    "tmy_datetime_index",
    "tmy_hour_calendar",
]

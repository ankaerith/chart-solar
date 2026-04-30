"""IrradianceProvider port + auto-router.

Adapters live in subpackage modules (`nsrdb.py`, `pvgis.py`,
`openmeteo.py`); the engine talks to the `IrradianceProvider` Protocol
so a swap is one DI binding away. `pick_provider` routes by lat/lon:

* US                → NSRDB (NREL PSM3, free with API key)
* UK / Europe       → PVGIS (free, no key)
* anywhere else     → Open-Meteo (free fallback; paid Standard tier
                       behind `OPENMETEO_PAID_ENABLED`)

The router never returns `None`: Open-Meteo is the global fallback.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, runtime_checkable

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from backend.config import Settings
from backend.config import settings as _global_settings

IrradianceSource = Literal["nsrdb", "pvgis", "openmeteo"]

HOURS_PER_TMY = 8760

#: TMY anchor year. Non-leap (so the calendar is exactly 8760 hours)
#: and stable across calls — TmyData arrays are indexed against this
#: anchor in UTC, then localized at consumption time.
TMY_ANCHOR_YEAR = 2023


def _build_tmy_hour_calendar() -> tuple[tuple[int, bool, int], ...]:
    base = datetime(TMY_ANCHOR_YEAR, 1, 1, 0, tzinfo=UTC)
    return tuple(
        (when.month, when.weekday() < 5, when.hour)
        for when in (base + timedelta(hours=i) for i in range(HOURS_PER_TMY))
    )


_TMY_HOUR_CALENDAR: tuple[tuple[int, bool, int], ...] = _build_tmy_hour_calendar()


def tmy_hour_calendar() -> tuple[tuple[int, bool, int], ...]:
    """``(month, is_weekday, hour_of_day)`` for each of the 8760 TMY hours.

    Built once at module import; the same tuple is shared across every
    caller so the per-hour billing walks in tariff + export_credit reuse
    one allocation across an entire Monte Carlo run.
    """
    return _TMY_HOUR_CALENDAR


def tmy_datetime_index(timezone: str) -> pd.DatetimeIndex:
    """8760-hour DatetimeIndex localised to ``timezone``.

    Anchored at ``TMY_ANCHOR_YEAR-01-01 00:00 UTC`` and converted to the
    requested IANA zone — pvlib's ModelChain insists on a tz-aware
    index, and the synthetic-TMY clear-sky calls need the same shape.
    Built per call because the pandas index carries a timezone in its
    state; callers in tight loops should hoist the result.
    """
    base = datetime(TMY_ANCHOR_YEAR, 1, 1, 0, tzinfo=UTC)
    naive_hours = [base + timedelta(hours=i) for i in range(HOURS_PER_TMY)]
    return pd.DatetimeIndex(naive_hours).tz_convert(timezone)


class TmyData(BaseModel):
    """8760-hour Typical Meteorological Year for one location.

    All array fields are exactly `HOURS_PER_TMY` long, hour-aligned in
    the location's local time. `timezone` is the IANA name (e.g.
    `America/Los_Angeles`); pvlib expects this format.
    """

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    elevation_m: float
    timezone: str
    source: IrradianceSource
    fetched_at: datetime

    ghi_w_m2: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    dni_w_m2: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    dhi_w_m2: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    temp_air_c: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    wind_speed_m_s: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)

    @model_validator(mode="after")
    def _channels_align(self) -> TmyData:
        lengths = {
            "ghi_w_m2": len(self.ghi_w_m2),
            "dni_w_m2": len(self.dni_w_m2),
            "dhi_w_m2": len(self.dhi_w_m2),
            "temp_air_c": len(self.temp_air_c),
            "wind_speed_m_s": len(self.wind_speed_m_s),
        }
        if len(set(lengths.values())) != 1:
            raise ValueError(f"channel length mismatch: {lengths}")
        return self


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

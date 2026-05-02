"""TMY (Typical Meteorological Year) shared types and calendar helpers.

The engine's pure-math layers and the irradiance providers both speak
this shape — engine consumes the 8760-hour series; providers populate
it. Keeping the type and the calendar helpers here lets the engine
stay pure (no ``backend.providers`` imports) while every provider
adapter still talks the same ``TmyData`` shape.

The provider port (``IrradianceProvider``) and auto-router
(``pick_provider``) stay in ``backend.providers.irradiance``: they're
the IO side of the boundary and have to know about which adapter to
construct.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, model_validator

IrradianceSource = Literal["nsrdb", "pvgis", "openmeteo"]

HOURS_PER_TMY = 8760

#: TMY anchor year. Non-leap (so the calendar is exactly 8760 hours)
#: and stable across calls — TmyData arrays are indexed against this
#: anchor at local midnight Jan 1 of the location's timezone.
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

    Anchored at **local** ``TMY_ANCHOR_YEAR-01-01 00:00`` in the requested
    IANA zone — pvlib's ModelChain insists on a tz-aware index, and the
    synthetic-TMY clear-sky calls need the same shape. Built per call
    because the pandas index carries a timezone in its state; callers in
    tight loops should hoist the result.

    The index must be **local-time-anchored**: TMY arrays from every
    adapter (NSRDB requests ``utc=false``; PVGIS / Open-Meteo follow the
    same convention) place row 0 at local midnight Jan 1, not UTC
    midnight. Anchoring the index in UTC and ``tz_convert``-ing offsets
    every row by the timezone's UTC offset, putting solar noon out of
    phase with the irradiance peak — see chart-solar-9xi4.
    """
    naive = pd.DatetimeIndex(
        [datetime(TMY_ANCHOR_YEAR, 1, 1, 0) + timedelta(hours=i) for i in range(HOURS_PER_TMY)]
    )
    return naive.tz_localize(timezone, ambiguous=False, nonexistent="shift_forward")


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

    #: Monthly aggregates feeding ``engine.soiling`` (HSU model) and
    #: ``engine.snow`` (Townsend). Optional so older cached TMYs and
    #: adapters that don't carry the data (PVGIS) stay valid; the
    #: pvlib-backed steps no-op gracefully when the field is None.
    precipitation_mm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)
    snowfall_cm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)
    relative_humidity_pct_per_month: list[float] | None = Field(None, min_length=12, max_length=12)

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


__all__ = [
    "HOURS_PER_TMY",
    "IrradianceSource",
    "TMY_ANCHOR_YEAR",
    "TmyData",
    "tmy_datetime_index",
    "tmy_hour_calendar",
]

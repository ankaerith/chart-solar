"""ERA5-Land sibling adapter — monthly precipitation + snowfall.

Two of the primary irradiance providers (NREL PSM3 in
:mod:`backend.providers.irradiance.nsrdb` and JRC PVGIS in
:mod:`backend.providers.irradiance.pvgis`) ship hourly irradiance +
temperature + RH but not surface precipitation or snowfall. Soiling
and snow engine steps therefore no-op on US and EU sites unless
something else fills the ``precipitation_mm_per_month`` /
``snowfall_cm_per_month`` slots on ``TmyData``.

This adapter pulls those fields from ERA5-Land via Open-Meteo's archive
endpoint — the same host that backs the global-fallback TMY in
:mod:`backend.providers.irradiance.openmeteo`. Both NSRDB and PVGIS
call this after their main fetch, merging the result onto the
returned ``TmyData``. Closes chart-solar-qrhs (US / NSRDB sibling) and
chart-solar-p559 (UK + EU / PVGIS sibling).

The request is intentionally light: ``daily=precipitation_sum,snowfall_sum``
only — no hourly fields — so the sibling fetch costs much less than
the primary call it augments. Aggregation reuses
:func:`aggregate_daily_to_monthly_sum` so the calendar matches every
other provider.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from backend.infra.http import make_get
from backend.providers.irradiance._aggregation import aggregate_daily_to_monthly_sum

#: Open-Meteo's free archive endpoint — same host the global-fallback
#: provider uses. ERA5-Land coverage is global, so the US, EU, and
#: rest-of-world all hit the same dataset.
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class Era5LandAggregates(BaseModel):
    """Result of a sibling lookup: 12-month precip + snow series."""

    precipitation_mm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)
    snowfall_cm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)


class Era5LandProvider:
    """Sibling provider for monthly precipitation + snowfall.

    NSRDB and PVGIS both call this after their main fetch. The result
    merges directly onto ``TmyData``'s optional monthly fields — both
    stay ``None`` if the sibling fetch fails or returns an empty
    payload, in which case the soiling / snow engine steps no-op (the
    same fallback shape primary-only providers gave before the sibling
    existed).
    """

    name = "era5_land"

    def __init__(self) -> None:
        self._get = make_get(service="era5_land")

    async def fetch_monthly_aggregates(self, lat: float, lon: float) -> Era5LandAggregates:
        year = _representative_year()
        response = await self._get(
            OPENMETEO_ARCHIVE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": f"{year}-01-01",
                "end_date": f"{year}-12-31",
                "daily": "precipitation_sum,snowfall_sum",
                "timezone": "GMT",
            },
        )
        return parse_era5_land_payload(response.json())


def parse_era5_land_payload(payload: dict[str, Any]) -> Era5LandAggregates:
    """Parse the Open-Meteo daily archive payload into 12-month aggregates.

    Returns an empty result (both fields ``None``) when the payload is
    missing the daily block — same permissive shape as the global
    Open-Meteo TMY parser.
    """
    daily = payload.get("daily") or {}
    daily_dates = daily.get("time") or []
    monthly_precip = aggregate_daily_to_monthly_sum(daily_dates, daily.get("precipitation_sum"))
    # Open-Meteo's docs label the field ``snowfall_sum`` but the unit is
    # cm/day — same as the global-fallback path uses.
    monthly_snow = aggregate_daily_to_monthly_sum(daily_dates, daily.get("snowfall_sum"))
    return Era5LandAggregates(
        precipitation_mm_per_month=monthly_precip,
        snowfall_cm_per_month=monthly_snow,
    )


def _representative_year() -> int:
    """Same anchor year as the global-fallback Open-Meteo provider —
    keeps every call site on the same archive snapshot."""
    return date.today().year - 1


__all__ = [
    "OPENMETEO_ARCHIVE_URL",
    "Era5LandAggregates",
    "Era5LandProvider",
    "parse_era5_land_payload",
]

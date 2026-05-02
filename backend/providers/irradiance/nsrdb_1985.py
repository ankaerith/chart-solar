"""NSRDB-1985 sibling adapter — monthly precipitation + snowfall for US sites.

NREL's PSM3 (the dataset behind :mod:`backend.providers.irradiance.nsrdb`)
ships hourly irradiance + temperature + RH but not surface precipitation
or snowfall — those columns aren't in PSM3's attribute set. Soiling and
snow steps therefore no-op on US sites unless something else fills the
``precipitation_mm_per_month`` / ``snowfall_cm_per_month`` slots on
``TmyData``.

The bead (chart-solar-qrhs) names this sibling "NSRDB-1985" after the
legacy SAMSON station archive that historically carried monthly snow +
precipitation summaries. NREL doesn't expose that archive as a discrete
``developer.nrel.gov`` REST endpoint today, so this adapter pulls the
same fields from ERA5-Land via Open-Meteo's archive endpoint — same
source we use for the global-fallback TMY (chart-solar-ifv8) and for
the PVGIS sibling (chart-solar-p559). One source, two call sites,
identical aggregation rules.

The request is intentionally light: ``daily=precipitation_sum,snowfall_sum``
only — no hourly fields — so the sibling fetch costs much less than the
PSM3 call it augments. Aggregation reuses
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
#: provider uses. ERA5-Land coverage is global, so US lat/lons hit the
#: same data the IPCC AR6 cycle relies on.
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class Nsrdb1985Aggregates(BaseModel):
    """Result of a sibling lookup: 12-month precip + snow series."""

    precipitation_mm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)
    snowfall_cm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)


class Nsrdb1985Provider:
    """Sibling provider for monthly precipitation + snowfall on US sites.

    The PSM3 adapter (:class:`NsrdbProvider`) calls this after the main
    irradiance fetch. The result merges directly onto ``TmyData``'s
    optional monthly fields — both stay ``None`` if the sibling fetch
    fails or returns an empty payload, in which case the soiling / snow
    engine steps no-op (same fallback shape as PSM3 with no sibling at
    all).
    """

    name = "nsrdb_1985"

    def __init__(self) -> None:
        self._get = make_get(service="nsrdb_1985")

    async def fetch_monthly_aggregates(self, lat: float, lon: float) -> Nsrdb1985Aggregates:
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
        return parse_nsrdb_1985_payload(response.json())


def parse_nsrdb_1985_payload(payload: dict[str, Any]) -> Nsrdb1985Aggregates:
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
    return Nsrdb1985Aggregates(
        precipitation_mm_per_month=monthly_precip,
        snowfall_cm_per_month=monthly_snow,
    )


def _representative_year() -> int:
    """Same anchor year as the global-fallback Open-Meteo provider —
    keeps both call sites on the same archive snapshot."""
    return date.today().year - 1


__all__ = [
    "OPENMETEO_ARCHIVE_URL",
    "Nsrdb1985Aggregates",
    "Nsrdb1985Provider",
    "parse_nsrdb_1985_payload",
]

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
call this concurrently with their main fetch and merge the result
onto the returned ``TmyData``. Closes chart-solar-qrhs (US / NSRDB
sibling) and chart-solar-p559 (UK + EU / PVGIS sibling).

The request is intentionally light: ``daily=precipitation_sum,snowfall_sum``
only — no hourly fields — so the sibling fetch costs much less than
the primary call it augments. Aggregation reuses
:func:`aggregate_daily_to_monthly_sum` so the calendar matches every
other provider.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from backend.domain.tmy import TmyData
from backend.infra.http import make_get
from backend.infra.logging import get_logger
from backend.providers.irradiance._aggregation import (
    aggregate_daily_to_monthly_sum,
    representative_archive_year,
)

#: Open-Meteo's free archive endpoint — same host the global-fallback
#: provider uses. ERA5-Land coverage is global, so the US, EU, and
#: rest-of-world all hit the same dataset.
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

#: Service key for the breaker registry. Shared across every primary
#: provider that calls the sibling.
_SERVICE = "era5_land"

_log = get_logger(__name__)


class Era5LandAggregates(BaseModel):
    """Result of a sibling lookup: 12-month precip + snow series."""

    precipitation_mm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)
    snowfall_cm_per_month: list[float] | None = Field(None, min_length=12, max_length=12)


@runtime_checkable
class Era5LandSibling(Protocol):
    """Structural type for the sibling DI seam.

    Tests can pass any object that satisfies this Protocol — typically a
    no-op stub that returns empty aggregates — without inheriting from
    :class:`Era5LandProvider` or tripping ``# type: ignore``.
    """

    async def fetch_monthly_aggregates(self, lat: float, lon: float) -> Era5LandAggregates: ...


class Era5LandProvider:
    """Sibling provider for monthly precipitation + snowfall.

    NSRDB and PVGIS both call this concurrently with their main fetch.
    The result merges directly onto ``TmyData``'s optional monthly
    fields — both stay ``None`` if the sibling fetch fails or returns
    an empty payload, in which case the soiling / snow engine steps
    no-op (the same fallback shape primary-only providers gave before
    the sibling existed).
    """

    name = _SERVICE

    def __init__(self) -> None:
        self._get = make_get(service=_SERVICE)

    async def fetch_monthly_aggregates(self, lat: float, lon: float) -> Era5LandAggregates:
        year = representative_archive_year()
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


async def fetch_aggregates_with_primary(
    sibling: Era5LandSibling,
    primary: Awaitable[TmyData],
    *,
    lat: float,
    lon: float,
) -> TmyData:
    """Run the primary fetch and the sibling lookup concurrently, then
    merge the sibling's monthly precipitation + snowfall onto the
    primary's ``TmyData``.

    A sibling failure must not break the primary fetch — the homeowner's
    audit doesn't depend on snow/precip — so we log and return ``tmy``
    unchanged on any sibling exception. The engine's soiling / snow
    steps already no-op when those fields are unset. A primary failure
    propagates after cancelling the sibling task (avoids a pending-task
    leak).
    """
    primary_task = asyncio.ensure_future(primary)
    sibling_task = asyncio.create_task(sibling.fetch_monthly_aggregates(lat, lon))
    try:
        tmy = await primary_task
    except BaseException:
        sibling_task.cancel()
        raise
    try:
        agg = await sibling_task
    except Exception:  # noqa: BLE001 — sibling failure must not break the primary
        _log.warning("era5_land.sibling_fetch_failed", lat=lat, lon=lon, exc_info=True)
        return tmy
    return tmy.model_copy(
        update={
            "precipitation_mm_per_month": agg.precipitation_mm_per_month,
            "snowfall_cm_per_month": agg.snowfall_cm_per_month,
        }
    )


__all__ = [
    "OPENMETEO_ARCHIVE_URL",
    "Era5LandAggregates",
    "Era5LandProvider",
    "Era5LandSibling",
    "fetch_aggregates_with_primary",
    "parse_era5_land_payload",
]

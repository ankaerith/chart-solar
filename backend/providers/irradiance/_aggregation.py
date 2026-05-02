"""Daily-bucket + provider-anchor helpers for irradiance adapters.

The hourly-bucket calendar math (``HOURS_PER_MONTH_NON_LEAP``,
``aggregate_hourly_to_monthly_mean``) lives in ``backend.domain.calendar``
so the engine can share it without crossing the engine→providers
import boundary; this module re-exports the symbols every adapter
already imports from here, plus its own daily-aggregation +
archive-anchor helpers that don't fit on the engine side.
"""

from __future__ import annotations

from datetime import date

from backend.domain.calendar import HOURS_PER_MONTH_NON_LEAP as HOURS_PER_MONTH_NON_LEAP
from backend.domain.calendar import (
    aggregate_hourly_to_monthly_mean as aggregate_hourly_to_monthly_mean,
)


def aggregate_daily_to_monthly_sum(
    dates: list[str],
    values: list[float] | None,
) -> list[float] | None:
    """Sum a daily series into 12 monthly buckets keyed off ISO date strings.

    Returns ``None`` when the daily payload is missing or empty —
    callers leave the corresponding ``TmyData`` field unset and the
    engine no-ops.
    """
    if not values or not dates:
        return None
    if len(dates) != len(values):
        return None
    monthly = [0.0] * 12
    for date_str, value in zip(dates, values, strict=False):
        if value is None:
            continue
        month_idx = int(date_str[5:7]) - 1
        monthly[month_idx] += float(value)
    return monthly


def representative_archive_year() -> int:
    """Anchor year for Open-Meteo / ERA5-Land archive requests.

    Open-Meteo's archive lags by a few days, so the most recently
    completed calendar year is the safe choice. Both the global-fallback
    TMY (:mod:`backend.providers.irradiance.openmeteo`) and the ERA5-Land
    sibling (:mod:`backend.providers.irradiance.era5_land`) read off the
    same anchor — keep them aligned so cached responses can in principle
    share a snapshot.
    """
    return date.today().year - 1


__all__ = [
    "HOURS_PER_MONTH_NON_LEAP",
    "aggregate_daily_to_monthly_sum",
    "aggregate_hourly_to_monthly_mean",
    "representative_archive_year",
]

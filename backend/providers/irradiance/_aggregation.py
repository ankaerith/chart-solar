"""Shared monthly-aggregation helpers for irradiance providers.

Each adapter aggregates hourly / daily series into 12-month buckets to
populate the optional ``TmyData`` fields the soiling + snow steps
consume. Centralising the math here keeps every provider on the same
calendar — non-leap months-per-day counts, January-anchored — so a
mismatched-bucket bug can't slip into one adapter and silently diverge.
"""

from __future__ import annotations

from backend.providers.irradiance import HOURS_PER_TMY

#: Hours per month in a non-leap year, January-anchored. Mirrors the
#: TMY anchor calendar (see ``backend.providers.irradiance``).
HOURS_PER_MONTH_NON_LEAP: tuple[int, ...] = (
    31 * 24,
    28 * 24,
    31 * 24,
    30 * 24,
    31 * 24,
    30 * 24,
    31 * 24,
    31 * 24,
    30 * 24,
    31 * 24,
    30 * 24,
    31 * 24,
)


def aggregate_hourly_to_monthly_mean(values: list[float]) -> list[float]:
    """Average an 8760-hour series into 12 monthly means.

    Days-per-month is non-uniform; sum/count division below handles
    that correctly (raw averaging would weight each month equally and
    lose the short-Feb / long-summer skew).
    """
    if len(values) != HOURS_PER_TMY:
        raise ValueError(f"hourly series must have {HOURS_PER_TMY} entries; got {len(values)}")
    out: list[float] = []
    cursor = 0
    for hours in HOURS_PER_MONTH_NON_LEAP:
        chunk = values[cursor : cursor + hours]
        out.append(sum(chunk) / len(chunk))
        cursor += hours
    return out


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


__all__ = [
    "HOURS_PER_MONTH_NON_LEAP",
    "aggregate_daily_to_monthly_sum",
    "aggregate_hourly_to_monthly_mean",
]

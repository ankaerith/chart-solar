"""TMY-anchored calendar helpers shared by the engine and providers.

The TMY anchor is non-leap (see ``backend.domain.tmy.TMY_ANCHOR_YEAR``)
so the per-month hour count is fixed: ``HOURS_PER_MONTH_NON_LEAP``
sums to exactly 8760 and aligns one-to-one with every hourly TMY series
in the codebase.

``aggregate_hourly_to_monthly_*`` collapse 8760-element series into
12 monthly buckets — providers use them to populate ``TmyData``'s
monthly RH / precipitation / snowfall fields, ``engine.snow`` uses
them to derive monthly mean air temperature and monthly POA insolation.

``apply_monthly_factors`` projects a 12-element factor vector back
onto the 8760-hour series — used by the snow step to layer Townsend
monthly loss onto the hourly AC stream, and ready for ``engine.soiling``
when its pvlib wrapper lands.
"""

from __future__ import annotations

from backend.domain.tmy import HOURS_PER_TMY

#: Hours per calendar month for a non-leap year (Jan…Dec). Sum is 8760.
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
    """Average each calendar month's hours into a single value.

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


def aggregate_hourly_to_monthly_sum(values: list[float]) -> list[float]:
    """Sum each calendar month's hours.

    Used to derive monthly POA insolation (Wh/m²) by summing hourly
    POA irradiance (W/m² × 1 hour). Townsend's snow-loss model expects
    energy totals here, not mean power — feeding mean values pushes
    the formula deep into its saturated regime.
    """
    if len(values) != HOURS_PER_TMY:
        raise ValueError(f"hourly series must have {HOURS_PER_TMY} entries; got {len(values)}")
    out: list[float] = []
    cursor = 0
    for hours in HOURS_PER_MONTH_NON_LEAP:
        out.append(sum(values[cursor : cursor + hours]))
        cursor += hours
    return out


def apply_monthly_factors(
    *,
    hourly: list[float],
    monthly_factors: list[float],
) -> list[float]:
    """Multiply each hour by its calendar month's factor.

    ``monthly_factors[m]`` applies to every hour falling in month
    ``m + 1`` of the TMY anchor calendar.
    """
    if len(hourly) != HOURS_PER_TMY:
        raise ValueError(f"hourly series must have {HOURS_PER_TMY} entries; got {len(hourly)}")
    if len(monthly_factors) != 12:
        raise ValueError(f"monthly_factors must have 12 entries; got {len(monthly_factors)}")

    out: list[float] = []
    cursor = 0
    for month_index, hours in enumerate(HOURS_PER_MONTH_NON_LEAP):
        factor = monthly_factors[month_index]
        for hour in hourly[cursor : cursor + hours]:
            out.append(hour * factor)
        cursor += hours
    return out


__all__ = [
    "HOURS_PER_MONTH_NON_LEAP",
    "aggregate_hourly_to_monthly_mean",
    "aggregate_hourly_to_monthly_sum",
    "apply_monthly_factors",
]

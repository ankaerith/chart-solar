"""Shared calendar helpers for engine steps that mix monthly + hourly data.

The TMY anchor is non-leap (see ``backend.domain.tmy.TMY_ANCHOR_YEAR``)
so the per-month hour count is fixed and shared across every engine
step. ``apply_monthly_factors`` projects a 12-element factor vector
onto an 8760-element hourly series — the canonical pattern used by
``engine.snow`` (Townsend monthly loss) and, eventually,
``engine.soiling``.

These were extracted out of the (eventually parallel) snow + soiling
steps to satisfy the spirit of ``chart-solar-yitq``, which called for a
single helper module. The two steps that consume it diverge in their
inputs (snow needs POA + RH + air temp; soiling needs precipitation +
RH + PM data) but converge here on the post-pvlib derate application.
"""

from __future__ import annotations

from backend.domain.tmy import HOURS_PER_TMY

#: Hours per month for a non-leap year (Jan…Dec). The TMY anchor is
#: explicitly non-leap (see ``TMY_ANCHOR_YEAR``) so this tuple aligns
#: 1-to-1 with the 8760 hourly series. Sum is exactly 8760.
HOURS_PER_MONTH_NON_LEAP: tuple[int, ...] = (
    744,  # Jan (31 × 24)
    672,  # Feb (28 × 24)
    744,  # Mar
    720,  # Apr
    744,  # May
    720,  # Jun
    744,  # Jul
    744,  # Aug
    720,  # Sep
    744,  # Oct
    720,  # Nov
    744,  # Dec
)


def _validate_hourly(hourly: list[float]) -> None:
    if len(hourly) != HOURS_PER_TMY:
        raise ValueError(f"hourly series must be {HOURS_PER_TMY} entries (got {len(hourly)})")


def _validate_monthly(monthly: list[float], name: str) -> None:
    if len(monthly) != 12:
        raise ValueError(f"{name} must be 12 entries (got {len(monthly)})")


def apply_monthly_factors(
    *,
    hourly: list[float],
    monthly_factors: list[float],
) -> list[float]:
    """Multiply each hour by its calendar month's factor.

    ``monthly_factors[m]`` applies to every hour falling in month
    ``m + 1`` of the TMY anchor calendar. Used by ``engine.snow`` to
    layer Townsend monthly loss onto the hourly AC production stream;
    the same shape will serve ``engine.soiling`` once it lands.
    """
    _validate_hourly(hourly)
    _validate_monthly(monthly_factors, "monthly_factors")

    out: list[float] = []
    cursor = 0
    for month_index, hours in enumerate(HOURS_PER_MONTH_NON_LEAP):
        factor = monthly_factors[month_index]
        for hour in hourly[cursor : cursor + hours]:
            out.append(hour * factor)
        cursor += hours
    return out


def aggregate_hourly_to_monthly_mean(hourly: list[float]) -> list[float]:
    """Average each calendar month's hours into a single value.

    Used by ``engine.snow`` to derive monthly mean air temperature from
    the hourly TMY before calling ``pvlib.snow.loss_townsend``.
    """
    _validate_hourly(hourly)

    out: list[float] = []
    cursor = 0
    for hours in HOURS_PER_MONTH_NON_LEAP:
        slice_ = hourly[cursor : cursor + hours]
        out.append(sum(slice_) / hours)
        cursor += hours
    return out


def aggregate_hourly_to_monthly_sum(hourly: list[float]) -> list[float]:
    """Sum each calendar month's hours.

    Used by ``engine.snow`` to derive monthly POA insolation (Wh/m²) by
    summing hourly POA irradiance (W/m² × 1 hour). Townsend's model
    expects energy totals here, not mean power — feeding mean values
    pushes the snow-loss formula into its saturated regime.
    """
    _validate_hourly(hourly)

    out: list[float] = []
    cursor = 0
    for hours in HOURS_PER_MONTH_NON_LEAP:
        out.append(sum(hourly[cursor : cursor + hours]))
        cursor += hours
    return out


__all__ = [
    "HOURS_PER_MONTH_NON_LEAP",
    "aggregate_hourly_to_monthly_mean",
    "aggregate_hourly_to_monthly_sum",
    "apply_monthly_factors",
]

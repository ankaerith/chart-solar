"""Tariff billing: flat + tiered + simple-TOU.

Bills an 8760-hour net-load array (positive = grid import) against a
``TariffSchedule``. The three structures it handles directly are:

* **flat** — single $/kWh rate, plus the fixed monthly charge.
* **tiered** — stepped rate where each month's first ``up_to`` kWh
  bills at one rate, the next block at another, etc. Catch-all top
  tier handles whatever's above the highest threshold.
* **tou** — time-of-use bands keyed by month + weekday + hour-of-day.
  Each hour matches the first band whose mask covers it; bands are
  expected to be non-overlapping. We don't sort by rate — the
  tariff's authoring convention is the source of truth.

Export credits (NEM 1:1 / NEM 3.0 NBT / UK SEG) are deferred to
``engine.export_credit`` per chart-solar-cvn — this step treats
negative net load (grid export) as zero kWh imported, so a
solar-rich household's bill collapses to just the fixed charge.

Net-metering 1:1 *can* be approximated here by feeding net load
through unchanged (export reduces import); the engine pipeline
chooses which path to wire based on the user's jurisdiction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.domain.tariff import (
    CurrencyCode,
    TariffSchedule,
    TieredBlock,
    TouPeriod,
    first_matching_tou_period,
)
from backend.domain.tmy import HOURS_PER_TMY, tmy_hour_calendar
from backend.engine.registry import register

_TMY_CALENDAR = tmy_hour_calendar()


class MonthlyBill(BaseModel):
    """One month's energy + fixed charge breakdown."""

    month: int = Field(..., ge=1, le=12)
    kwh_imported: float = Field(..., ge=0.0)
    energy_charge: float = Field(..., ge=0.0)
    fixed_charge: float = Field(..., ge=0.0)
    total: float = Field(..., ge=0.0)


class AnnualBill(BaseModel):
    """12 monthly bills + roll-up totals."""

    currency: CurrencyCode
    monthly: list[MonthlyBill] = Field(..., min_length=12, max_length=12)
    annual_kwh_imported: float = Field(..., ge=0.0)
    annual_energy_charge: float = Field(..., ge=0.0)
    annual_fixed_charge: float = Field(..., ge=0.0)
    annual_total: float = Field(..., ge=0.0)


def _bill_flat(
    *, hourly_import_kwh: list[float], rate_per_kwh: float
) -> tuple[list[float], list[float]]:
    """Per-month (energy_charge, kwh_imported) for a flat-rate tariff."""
    monthly_energy = [0.0] * 12
    monthly_kwh = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import_kwh):
        month_idx = _TMY_CALENDAR[hour_index][0] - 1
        monthly_kwh[month_idx] += kwh
        monthly_energy[month_idx] += kwh * rate_per_kwh
    return monthly_energy, monthly_kwh


def sort_tiered_blocks(tariff: TariffSchedule) -> list[TieredBlock]:
    """Threshold-ascending block order, with the catch-all (no
    ``up_to_kwh_per_month``) last via the ``inf`` key.

    Hoisted out of the per-month walk so callers running it inside a
    loop (Monte Carlo × hold years × 12 months) sort once instead of
    on every walk.
    """
    if not tariff.tiered_blocks:
        raise ValueError("tiered tariff requires tiered_blocks")
    return sorted(
        tariff.tiered_blocks,
        key=lambda b: b.up_to_kwh_per_month if b.up_to_kwh_per_month is not None else float("inf"),
    )


def walk_tier_charge(monthly_kwh: float, sorted_blocks: list[TieredBlock]) -> float:
    """Bill ``monthly_kwh`` (clamped at 0) through pre-sorted tier blocks.

    The cursor walk on the monthly total is mathematically equivalent
    to walking hour-by-hour because no per-hour artifact is reported —
    only the month's total energy charge is.
    """
    if monthly_kwh <= 0:
        return 0.0
    cursor = 0.0
    remaining = monthly_kwh
    charge = 0.0
    for block in sorted_blocks:
        if remaining <= 0:
            break
        threshold = block.up_to_kwh_per_month
        if threshold is None:
            charge += remaining * block.rate_per_kwh
            return charge
        if cursor >= threshold:
            continue
        portion = min(remaining, threshold - cursor)
        charge += portion * block.rate_per_kwh
        cursor += portion
        remaining -= portion
    return charge


def _bill_tiered(
    *,
    hourly_import_kwh: list[float],
    tariff: TariffSchedule,
) -> tuple[list[float], list[float]]:
    """Per-month (energy_charge, kwh_imported) for a tiered tariff."""
    sorted_blocks = sort_tiered_blocks(tariff)
    monthly_kwh = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import_kwh):
        if kwh > 0:
            monthly_kwh[_TMY_CALENDAR[hour_index][0] - 1] += kwh
    monthly_energy = [walk_tier_charge(m, sorted_blocks) for m in monthly_kwh]
    return monthly_energy, monthly_kwh


def build_tou_rate_cache(periods: list[TouPeriod]) -> dict[tuple[int, bool, int], float]:
    """Memoise ``(month, is_weekday, hour_of_day) → rate_per_kwh`` once.

    There are only 12 × 2 × 24 = 576 distinct cells across an 8760-hour
    year, so a one-shot scan over the unique cells is many orders of
    magnitude cheaper than re-scanning ``periods`` 8760 × N times for
    every Monte Carlo path × finance scenario.

    Cells with no matching period are absent from the dict — callers
    raise on miss to surface incomplete tariffs as a clear error rather
    than silently zeroing out billing.
    """
    cache: dict[tuple[int, bool, int], float] = {}
    for month in range(1, 13):
        for is_weekday in (True, False):
            for hour_of_day in range(24):
                period = first_matching_tou_period(
                    periods,
                    month=month,
                    is_weekday=is_weekday,
                    hour_of_day=hour_of_day,
                )
                if period is not None:
                    cache[(month, is_weekday, hour_of_day)] = period.rate_per_kwh
    return cache


def _bill_tou(
    *,
    hourly_import_kwh: list[float],
    tariff: TariffSchedule,
) -> tuple[list[float], list[float]]:
    """Per-month (energy_charge, kwh_imported) for a TOU tariff."""
    periods = tariff.tou_periods
    if not periods:
        raise ValueError("tou tariff requires tou_periods")

    rate_cache = build_tou_rate_cache(periods)
    monthly_energy = [0.0] * 12
    monthly_kwh = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import_kwh):
        if kwh <= 0:
            continue
        cell = _TMY_CALENDAR[hour_index]
        rate = rate_cache.get(cell)
        if rate is None:
            month, is_weekday, hour_of_day = cell
            raise ValueError(
                f"no TOU period matches hour_index={hour_index} "
                f"(month={month}, is_weekday={is_weekday}, hour={hour_of_day})"
            )
        monthly_kwh[cell[0] - 1] += kwh
        monthly_energy[cell[0] - 1] += kwh * rate
    return monthly_energy, monthly_kwh


@register("engine.tariff")
def compute_annual_bill(
    *,
    hourly_net_load_kwh: list[float],
    tariff: TariffSchedule,
) -> AnnualBill:
    """Bill 8760 hours of net load against a tariff schedule.

    Negative entries (grid export) are treated as zero for billing —
    export credits live in ``engine.export_credit``. For NEM 1:1 sites
    the caller pre-nets the array; for NEM 3.0 / NBT, the export
    credit is computed separately and netted against this bill at the
    monthly true-up.
    """
    if len(hourly_net_load_kwh) != HOURS_PER_TMY:
        raise ValueError(
            f"hourly_net_load_kwh must be {HOURS_PER_TMY} entries (got {len(hourly_net_load_kwh)})"
        )

    hourly_import = [max(0.0, kwh) for kwh in hourly_net_load_kwh]

    if tariff.structure == "flat":
        if tariff.flat_rate_per_kwh is None:
            raise ValueError("flat tariff requires flat_rate_per_kwh")
        monthly_energy, monthly_kwh = _bill_flat(
            hourly_import_kwh=hourly_import,
            rate_per_kwh=tariff.flat_rate_per_kwh,
        )
    elif tariff.structure == "tiered":
        monthly_energy, monthly_kwh = _bill_tiered(hourly_import_kwh=hourly_import, tariff=tariff)
    elif tariff.structure == "tou":
        monthly_energy, monthly_kwh = _bill_tou(hourly_import_kwh=hourly_import, tariff=tariff)
    else:
        raise ValueError(f"unknown tariff structure: {tariff.structure!r}")

    fixed_per_month = tariff.fixed_monthly_charge
    monthly_bills = [
        MonthlyBill(
            month=m + 1,
            kwh_imported=monthly_kwh[m],
            energy_charge=monthly_energy[m],
            fixed_charge=fixed_per_month,
            total=monthly_energy[m] + fixed_per_month,
        )
        for m in range(12)
    ]
    return AnnualBill(
        currency=tariff.currency,
        monthly=monthly_bills,
        annual_kwh_imported=sum(monthly_kwh),
        annual_energy_charge=sum(monthly_energy),
        annual_fixed_charge=fixed_per_month * 12,
        annual_total=sum(b.total for b in monthly_bills),
    )

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

from backend.engine.registry import register
from backend.providers.irradiance import HOURS_PER_TMY, tmy_hour_calendar
from backend.providers.tariff import (
    CurrencyCode,
    TariffSchedule,
    first_matching_tou_period,
)

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


def _bill_tiered(
    *,
    hourly_import_kwh: list[float],
    tariff: TariffSchedule,
) -> tuple[list[float], list[float]]:
    """Per-month (energy_charge, kwh_imported) for a tiered tariff.

    Walks the hourly stream tracking month-to-date kWh; when a tier's
    threshold is crossed mid-hour, splits the kWh across the two
    tiers proportionally. The catch-all (no ``up_to_kwh_per_month``)
    sorts last via the `inf` key.
    """
    blocks = tariff.tiered_blocks
    if not blocks:
        raise ValueError("tiered tariff requires tiered_blocks")

    sorted_blocks = sorted(
        blocks,
        key=lambda b: b.up_to_kwh_per_month if b.up_to_kwh_per_month is not None else float("inf"),
    )

    monthly_energy = [0.0] * 12
    monthly_kwh = [0.0] * 12

    for hour_index, kwh in enumerate(hourly_import_kwh):
        if kwh <= 0:
            continue
        month_idx = _TMY_CALENDAR[hour_index][0] - 1
        monthly_kwh[month_idx] += kwh
        cursor = monthly_kwh[month_idx] - kwh
        remaining = kwh
        for block in sorted_blocks:
            if remaining <= 0:
                break
            threshold = block.up_to_kwh_per_month
            if threshold is None:
                monthly_energy[month_idx] += remaining * block.rate_per_kwh
                remaining = 0.0
                break
            if cursor >= threshold:
                continue
            portion = min(remaining, threshold - cursor)
            monthly_energy[month_idx] += portion * block.rate_per_kwh
            cursor += portion
            remaining -= portion

    return monthly_energy, monthly_kwh


def _bill_tou(
    *,
    hourly_import_kwh: list[float],
    tariff: TariffSchedule,
) -> tuple[list[float], list[float]]:
    """Per-month (energy_charge, kwh_imported) for a TOU tariff."""
    periods = tariff.tou_periods
    if not periods:
        raise ValueError("tou tariff requires tou_periods")

    monthly_energy = [0.0] * 12
    monthly_kwh = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import_kwh):
        if kwh <= 0:
            continue
        month, is_weekday, hour_of_day = _TMY_CALENDAR[hour_index]
        period = first_matching_tou_period(
            periods,
            month=month,
            is_weekday=is_weekday,
            hour_of_day=hour_of_day,
        )
        if period is None:
            raise ValueError(
                f"no TOU period matches hour_index={hour_index} "
                f"(month={month}, is_weekday={is_weekday}, hour={hour_of_day})"
            )
        monthly_kwh[month - 1] += kwh
        monthly_energy[month - 1] += kwh * period.rate_per_kwh
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

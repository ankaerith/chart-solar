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

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from backend.providers.tariff import (
    CurrencyCode,
    TariffSchedule,
    TouPeriod,
)

HOURS_PER_TMY = 8760


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


def _hour_to_calendar(
    hour_index: int,
    *,
    year: int = 2023,
) -> tuple[int, bool, int]:
    """Map a 0..8759 hour index to (month_1_indexed, is_weekday, hour_of_day).

    Year 2023 is a non-leap year so the index lines up with TmyData.
    """
    base = datetime(year, 1, 1, 0, tzinfo=UTC)
    when = base + timedelta(hours=hour_index)
    return when.month, when.weekday() < 5, when.hour


def _matching_tou_period(
    *,
    periods: list[TouPeriod],
    month: int,
    is_weekday: bool,
    hour_of_day: int,
) -> TouPeriod | None:
    """First period whose month list + weekday flag + hour mask all
    cover the given hour. ``None`` when no period matches — caller
    decides how to handle (we raise; an unmatched hour is a tariff
    authoring bug)."""
    for period in periods:
        if month not in period.months:
            continue
        if period.is_weekday is not is_weekday:
            continue
        if period.hour_mask[hour_of_day]:
            return period
    return None


def _bill_flat(*, hourly_import_kwh: list[float], rate_per_kwh: float) -> list[float]:
    """Per-month energy charges for a flat-rate tariff."""
    monthly_energy = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import_kwh):
        month, _, _ = _hour_to_calendar(hour_index)
        monthly_energy[month - 1] += kwh * rate_per_kwh
    return monthly_energy


def _bill_tiered(
    *,
    hourly_import_kwh: list[float],
    tariff: TariffSchedule,
) -> list[float]:
    """Per-month energy charges for a tiered tariff.

    Walks the hourly stream tracking month-to-date kWh; when a tier's
    threshold is crossed mid-hour, splits the kWh across the two
    tiers proportionally. The catch-all (no ``up_to_kwh_per_month``)
    handles everything above the last threshold.
    """
    blocks = tariff.tiered_blocks
    if not blocks:
        raise ValueError("tiered tariff requires tiered_blocks")

    # Sort blocks by threshold so we can walk them in order; the
    # catch-all (None threshold) goes last by virtue of `inf` sort key.
    sorted_blocks = sorted(
        blocks,
        key=lambda b: b.up_to_kwh_per_month if b.up_to_kwh_per_month is not None else float("inf"),
    )

    monthly_energy = [0.0] * 12
    monthly_kwh_so_far = [0.0] * 12

    for hour_index, kwh in enumerate(hourly_import_kwh):
        if kwh <= 0:
            continue
        month, _, _ = _hour_to_calendar(hour_index)
        cursor = monthly_kwh_so_far[month - 1]
        remaining = kwh
        for block in sorted_blocks:
            if remaining <= 0:
                break
            threshold = block.up_to_kwh_per_month
            if threshold is None:
                # Catch-all — bill everything left at this rate.
                monthly_energy[month - 1] += remaining * block.rate_per_kwh
                cursor += remaining
                remaining = 0.0
                break
            if cursor >= threshold:
                continue
            available = threshold - cursor
            portion = min(remaining, available)
            monthly_energy[month - 1] += portion * block.rate_per_kwh
            cursor += portion
            remaining -= portion
        monthly_kwh_so_far[month - 1] = cursor

    return monthly_energy


def _bill_tou(
    *,
    hourly_import_kwh: list[float],
    tariff: TariffSchedule,
) -> list[float]:
    """Per-month energy charges for a TOU tariff."""
    periods = tariff.tou_periods
    if not periods:
        raise ValueError("tou tariff requires tou_periods")

    monthly_energy = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import_kwh):
        if kwh <= 0:
            continue
        month, is_weekday, hour_of_day = _hour_to_calendar(hour_index)
        period = _matching_tou_period(
            periods=periods,
            month=month,
            is_weekday=is_weekday,
            hour_of_day=hour_of_day,
        )
        if period is None:
            raise ValueError(
                f"no TOU period matches hour_index={hour_index} "
                f"(month={month}, is_weekday={is_weekday}, hour={hour_of_day})"
            )
        monthly_energy[month - 1] += kwh * period.rate_per_kwh
    return monthly_energy


def compute_annual_bill(
    *,
    hourly_net_load_kwh: list[float],
    tariff: TariffSchedule,
) -> AnnualBill:
    """Bill 8760 hours of net load against a tariff schedule.

    Negative entries (grid export) are treated as zero for billing —
    export credits live in ``engine.export_credit`` (chart-solar-cvn).
    For NEM 1:1 sites, the caller can pre-net the array and pass
    ``max(net_load, 0)`` separately, or feed signed net load straight
    through (negative entries collapse to zero so an over-producing
    month bottoms out at the fixed charge).
    """
    if len(hourly_net_load_kwh) != HOURS_PER_TMY:
        raise ValueError(
            f"hourly_net_load_kwh must be {HOURS_PER_TMY} entries "
            f"(got {len(hourly_net_load_kwh)})"
        )

    hourly_import = [max(0.0, kwh) for kwh in hourly_net_load_kwh]

    if tariff.structure == "flat":
        if tariff.flat_rate_per_kwh is None:
            raise ValueError("flat tariff requires flat_rate_per_kwh")
        monthly_energy = _bill_flat(
            hourly_import_kwh=hourly_import,
            rate_per_kwh=tariff.flat_rate_per_kwh,
        )
    elif tariff.structure == "tiered":
        monthly_energy = _bill_tiered(hourly_import_kwh=hourly_import, tariff=tariff)
    elif tariff.structure == "tou":
        monthly_energy = _bill_tou(hourly_import_kwh=hourly_import, tariff=tariff)
    else:
        raise ValueError(f"unknown tariff structure: {tariff.structure!r}")

    monthly_kwh = [0.0] * 12
    for hour_index, kwh in enumerate(hourly_import):
        month, _, _ = _hour_to_calendar(hour_index)
        monthly_kwh[month - 1] += kwh

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

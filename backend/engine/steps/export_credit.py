"""Export-credit modeling: NEM 1:1, NEM 3.0 / NBT, UK SEG.

When a household exports power to the grid (production exceeds load
in that hour), the regulator's compensation rule decides what that
kWh is worth back to the homeowner:

* **NEM 1:1** — retail-rate net metering. Every exported kWh credits
  at the same rate it would have cost to import in that hour. The
  classic "spinning meter backwards" model; pre-2023 in California,
  still active in most US states.
* **NEM 3.0 / NBT** — California's Net Billing Tariff. Each hour
  carries a regulator-published "avoided cost" vector (CPUC ACC) and
  exports credit at *that* rate, which is typically 5-15× lower than
  retail. Drops residential payback by years.
* **UK SEG (Smart Export Guarantee)** — supplier-set rate (Octopus
  Outgoing ~15p/kWh, E.ON Next ~3p, etc.). Most are flat; some have
  TOU variants. We model the flat rate here; TOU SEG is the same
  shape as NBT (an hourly rate vector).

This step is pure-math. The hourly avoided-cost vector for NBT is the
job of chart-solar-ma7 (CPUC ACC ingest); this module just consumes
it. Likewise the SEG rate registry (per-supplier defaults) is part of
the data layer (chart-solar-ltx).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from backend.providers.tariff import TariffSchedule, TouPeriod

HOURS_PER_TMY = 8760

ExportRegime = Literal["nem_one_for_one", "nem_three_nbt", "seg_flat", "seg_tou"]


class ExportCreditResult(BaseModel):
    """Per-month + annual export-credit dollar amounts."""

    regime: ExportRegime
    monthly_credit: list[float] = Field(..., min_length=12, max_length=12)
    annual_credit: float = Field(..., ge=0.0)
    annual_kwh_exported: float = Field(..., ge=0.0)


def _hour_to_month(hour_index: int, *, year: int = 2023) -> int:
    """0..8759 → 1..12 month index (year 2023 = non-leap, aligns w/ TmyData)."""
    base = datetime(year, 1, 1, 0, tzinfo=UTC)
    return (base + timedelta(hours=hour_index)).month


def _validate_hourly(hourly: list[float], *, name: str) -> None:
    if len(hourly) != HOURS_PER_TMY:
        raise ValueError(
            f"{name} must be {HOURS_PER_TMY} entries (got {len(hourly)})"
        )


def apply_nem_three_nbt(
    *,
    hourly_export_kwh: list[float],
    hourly_avoided_cost_per_kwh: list[float],
) -> ExportCreditResult:
    """Credit each hour of export at the CPUC ACC vector's matching hour.

    Both arrays must be 8760 entries. Negative export entries are
    clamped at zero (defense against caller passing signed net load).
    Negative ACC values *are* allowed — CPUC's vector occasionally
    dips negative during midday glut, and the homeowner does pay for
    exporting in those hours under NBT (yes, really).
    """
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")
    _validate_hourly(hourly_avoided_cost_per_kwh, name="hourly_avoided_cost_per_kwh")

    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, (export_kwh, rate) in enumerate(
        zip(hourly_export_kwh, hourly_avoided_cost_per_kwh, strict=True)
    ):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        month = _hour_to_month(hour_index)
        monthly[month - 1] += kwh * rate
        total_kwh += kwh

    return ExportCreditResult(
        regime="nem_three_nbt",
        monthly_credit=monthly,
        annual_credit=max(0.0, sum(monthly)),
        annual_kwh_exported=total_kwh,
    )


def apply_seg_flat(
    *,
    hourly_export_kwh: list[float],
    rate_per_kwh: float,
) -> ExportCreditResult:
    """UK SEG with a single flat rate (Octopus Outgoing flat, E.ON
    Next, etc.). Octopus's TOU SEG goes through ``apply_seg_tou``."""
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")
    if rate_per_kwh < 0:
        raise ValueError("rate_per_kwh must be >= 0")

    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, export_kwh in enumerate(hourly_export_kwh):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        month = _hour_to_month(hour_index)
        monthly[month - 1] += kwh * rate_per_kwh
        total_kwh += kwh

    return ExportCreditResult(
        regime="seg_flat",
        monthly_credit=monthly,
        annual_credit=sum(monthly),
        annual_kwh_exported=total_kwh,
    )


def apply_seg_tou(
    *,
    hourly_export_kwh: list[float],
    hourly_rate_per_kwh: list[float],
) -> ExportCreditResult:
    """UK SEG with a TOU rate vector (Octopus Agile-style — half-hourly
    settlement, but we average to hourly for the engine).

    Mathematically identical to NBT, but recorded under a different
    regime tag so the audit can surface "you're on a UK-style export
    rate" vs "California NBT" when explaining the credit math.
    """
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")
    _validate_hourly(hourly_rate_per_kwh, name="hourly_rate_per_kwh")

    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, (export_kwh, rate) in enumerate(
        zip(hourly_export_kwh, hourly_rate_per_kwh, strict=True)
    ):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        month = _hour_to_month(hour_index)
        monthly[month - 1] += kwh * rate
        total_kwh += kwh

    return ExportCreditResult(
        regime="seg_tou",
        monthly_credit=monthly,
        annual_credit=max(0.0, sum(monthly)),
        annual_kwh_exported=total_kwh,
    )


def _matching_tou_rate(
    *,
    periods: list[TouPeriod],
    month: int,
    is_weekday: bool,
    hour_of_day: int,
) -> float | None:
    for period in periods:
        if month not in period.months:
            continue
        if period.is_weekday is not is_weekday:
            continue
        if period.hour_mask[hour_of_day]:
            return period.rate_per_kwh
    return None


def _hour_calendar(hour_index: int, *, year: int = 2023) -> tuple[int, bool, int]:
    base = datetime(year, 1, 1, 0, tzinfo=UTC)
    when = base + timedelta(hours=hour_index)
    return when.month, when.weekday() < 5, when.hour


def apply_nem_one_for_one(
    *,
    hourly_export_kwh: list[float],
    tariff: TariffSchedule,
) -> ExportCreditResult:
    """NEM 1:1 retail-rate net metering.

    Each exported kWh credits at *the rate it would have cost to
    import in that hour*. For flat tariffs that's the single
    flat_rate_per_kwh; for TOU tariffs it's the band's rate. Tiered
    NEM 1:1 is unusual in practice — the credit reduces the
    customer's net consumption before tier walking — so we credit at
    the highest tier rate as a conservative upper bound (i.e. the
    homeowner's marginal $/kWh saved by avoiding import).
    """
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")

    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, export_kwh in enumerate(hourly_export_kwh):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        month, is_weekday, hour_of_day = _hour_calendar(hour_index)
        if tariff.structure == "flat":
            rate = tariff.flat_rate_per_kwh or 0.0
        elif tariff.structure == "tou":
            assert tariff.tou_periods is not None
            matched = _matching_tou_rate(
                periods=tariff.tou_periods,
                month=month,
                is_weekday=is_weekday,
                hour_of_day=hour_of_day,
            )
            if matched is None:
                raise ValueError(
                    f"NEM 1:1 needs a TOU rate at hour_index={hour_index} "
                    f"(month={month}, weekday={is_weekday}, hour={hour_of_day}) "
                    "but no period matched — check tariff coverage"
                )
            rate = matched
        elif tariff.structure == "tiered":
            assert tariff.tiered_blocks
            rate = max(b.rate_per_kwh for b in tariff.tiered_blocks)
        else:
            raise ValueError(f"unknown tariff structure: {tariff.structure!r}")
        monthly[month - 1] += kwh * rate
        total_kwh += kwh

    return ExportCreditResult(
        regime="nem_one_for_one",
        monthly_credit=monthly,
        annual_credit=sum(monthly),
        annual_kwh_exported=total_kwh,
    )

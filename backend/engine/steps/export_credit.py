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
  TOU variants. The TOU shape is identical to NBT.

This step is pure-math. The hourly avoided-cost vector for NBT and
the SEG supplier rate registry are part of the data layer; this
module just consumes them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.registry import register
from backend.engine.types import ExportRegime
from backend.providers.irradiance import HOURS_PER_TMY, tmy_hour_calendar
from backend.providers.tariff import TariffSchedule, first_matching_tou_period

_TMY_CALENDAR = tmy_hour_calendar()


class ExportCreditResult(BaseModel):
    """Per-month + annual export-credit dollar amounts.

    ``monthly_credit`` entries can go negative under NBT / SEG-TOU when
    the rate vector dips below zero (CPUC's spring-glut hours).
    ``annual_credit`` is also signed — callers that want a bill-impact
    number can floor at zero themselves.
    """

    regime: ExportRegime
    monthly_credit: list[float] = Field(..., min_length=12, max_length=12)
    annual_credit: float
    annual_kwh_exported: float = Field(..., ge=0.0)


def _validate_hourly(hourly: list[float], *, name: str) -> None:
    if len(hourly) != HOURS_PER_TMY:
        raise ValueError(f"{name} must be {HOURS_PER_TMY} entries (got {len(hourly)})")


def _accumulate_monthly_credits(
    hourly_export_kwh: list[float],
    rate_for_hour: list[float],
) -> tuple[list[float], float]:
    """Walk the export stream once, accumulating per-month credit and
    total exported kWh. Caller passes a same-length list of per-hour
    rates."""
    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, export_kwh in enumerate(hourly_export_kwh):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        monthly[_TMY_CALENDAR[hour_index][0] - 1] += kwh * rate_for_hour[hour_index]
        total_kwh += kwh
    return monthly, total_kwh


def apply_nem_three_nbt(
    *,
    hourly_export_kwh: list[float],
    hourly_avoided_cost_per_kwh: list[float],
) -> ExportCreditResult:
    """Credit each hour of export at the CPUC ACC vector's matching hour.

    Both arrays must be 8760 entries. Negative ACC values *are* allowed
    — CPUC's vector occasionally dips negative during midday glut, and
    the homeowner does pay for exporting in those hours under NBT (yes,
    really).
    """
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")
    _validate_hourly(hourly_avoided_cost_per_kwh, name="hourly_avoided_cost_per_kwh")
    monthly, total_kwh = _accumulate_monthly_credits(hourly_export_kwh, hourly_avoided_cost_per_kwh)
    return ExportCreditResult(
        regime="nem_three_nbt",
        monthly_credit=monthly,
        annual_credit=sum(monthly),
        annual_kwh_exported=total_kwh,
    )


def apply_seg_flat(
    *,
    hourly_export_kwh: list[float],
    rate_per_kwh: float,
) -> ExportCreditResult:
    """UK SEG with a single flat rate (Octopus Outgoing flat, E.ON Next,
    etc.). Octopus's TOU SEG goes through ``apply_seg_tou``."""
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")
    if rate_per_kwh < 0:
        raise ValueError("rate_per_kwh must be >= 0")
    monthly, total_kwh = _accumulate_monthly_credits(
        hourly_export_kwh, [rate_per_kwh] * HOURS_PER_TMY
    )
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
    monthly, total_kwh = _accumulate_monthly_credits(hourly_export_kwh, hourly_rate_per_kwh)
    return ExportCreditResult(
        regime="seg_tou",
        monthly_credit=monthly,
        annual_credit=sum(monthly),
        annual_kwh_exported=total_kwh,
    )


def _resolve_nem_one_rate(
    *,
    tariff: TariffSchedule,
    month: int,
    is_weekday: bool,
    hour_of_day: int,
    hour_index: int,
) -> float:
    """The hour's marginal retail rate under NEM 1:1: the rate the
    homeowner would have paid had they imported instead of exported."""
    if tariff.structure == "flat":
        return tariff.flat_rate_per_kwh or 0.0
    if tariff.structure == "tou":
        if not tariff.tou_periods:
            raise ValueError("tou tariff requires tou_periods")
        matched = first_matching_tou_period(
            tariff.tou_periods,
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
        return matched.rate_per_kwh
    if tariff.structure == "tiered":
        if not tariff.tiered_blocks:
            raise ValueError("tiered tariff requires tiered_blocks")
        # Conservative upper bound — the marginal $/kWh saved by
        # avoiding an import is the top tier's rate.
        return max(b.rate_per_kwh for b in tariff.tiered_blocks)
    raise ValueError(f"unknown tariff structure: {tariff.structure!r}")


def apply_nem_one_for_one(
    *,
    hourly_export_kwh: list[float],
    tariff: TariffSchedule,
) -> ExportCreditResult:
    """NEM 1:1 retail-rate net metering.

    Each exported kWh credits at the rate it would have cost to import
    in that hour. Tiered NEM 1:1 credits at the top tier's rate — the
    conservative upper bound on the homeowner's marginal saving.
    """
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")

    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, export_kwh in enumerate(hourly_export_kwh):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        month, is_weekday, hour_of_day = _TMY_CALENDAR[hour_index]
        rate = _resolve_nem_one_rate(
            tariff=tariff,
            month=month,
            is_weekday=is_weekday,
            hour_of_day=hour_of_day,
            hour_index=hour_index,
        )
        monthly[month - 1] += kwh * rate
        total_kwh += kwh
    return ExportCreditResult(
        regime="nem_one_for_one",
        monthly_credit=monthly,
        annual_credit=sum(monthly),
        annual_kwh_exported=total_kwh,
    )


@register("engine.export_credit")
def apply_export_credit(
    *,
    regime: ExportRegime,
    hourly_export_kwh: list[float],
    tariff: TariffSchedule | None = None,
    hourly_avoided_cost_per_kwh: list[float] | None = None,
    hourly_rate_per_kwh: list[float] | None = None,
    rate_per_kwh: float | None = None,
) -> ExportCreditResult:
    """Single dispatch entry point for the four export-credit regimes.

    Each regime needs different inputs (NEM 1:1 reads back the import
    tariff; NBT and SEG-TOU need an hourly rate vector; SEG-flat needs
    a scalar). The pipeline registers this function under
    ``engine.export_credit`` and supplies the regime + the matching
    payload — keeping the registry single-keyed avoids the need to
    fan ``engine.export_credit.<regime>`` keys through tier configs.
    """
    if regime == "nem_one_for_one":
        if tariff is None:
            raise ValueError("nem_one_for_one regime requires `tariff`")
        return apply_nem_one_for_one(hourly_export_kwh=hourly_export_kwh, tariff=tariff)
    if regime == "nem_three_nbt":
        if hourly_avoided_cost_per_kwh is None:
            raise ValueError("nem_three_nbt regime requires `hourly_avoided_cost_per_kwh`")
        return apply_nem_three_nbt(
            hourly_export_kwh=hourly_export_kwh,
            hourly_avoided_cost_per_kwh=hourly_avoided_cost_per_kwh,
        )
    if regime == "seg_flat":
        if rate_per_kwh is None:
            raise ValueError("seg_flat regime requires `rate_per_kwh`")
        return apply_seg_flat(hourly_export_kwh=hourly_export_kwh, rate_per_kwh=rate_per_kwh)
    if regime == "seg_tou":
        if hourly_rate_per_kwh is None:
            raise ValueError("seg_tou regime requires `hourly_rate_per_kwh`")
        return apply_seg_tou(
            hourly_export_kwh=hourly_export_kwh,
            hourly_rate_per_kwh=hourly_rate_per_kwh,
        )
    raise ValueError(f"unknown export-credit regime: {regime!r}")

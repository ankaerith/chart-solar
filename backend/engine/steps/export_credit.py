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

Each regime is modelled as a Pydantic discriminated-union variant
that carries only its required inputs and its own ``apply()`` method.
The dispatcher (``apply_export_credit``) is a one-line delegator —
parse-time validation refuses bad combinations like "regime=seg_flat
with hourly_rate_per_kwh set" before the engine sees them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.registry import register
from backend.engine.steps.tariff import sort_tiered_blocks, walk_tier_charge
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


def _resolve_nem_one_rate_flat_or_tou(
    *,
    tariff: TariffSchedule,
    month: int,
    is_weekday: bool,
    hour_of_day: int,
    hour_index: int,
) -> float:
    """The hour's marginal retail rate under NEM 1:1 for flat / TOU
    tariffs. Tiered tariffs are billed via tier-walking netting in
    ``_apply_nem_one_for_one_tiered`` rather than per-hour rate lookup,
    because the marginal-displacement rate for an exported kWh under
    a tiered tariff depends on the month's cumulative-import position
    in the tier table — a per-hour rate doesn't exist.
    """
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
    raise ValueError(
        "tiered tariffs route through _apply_nem_one_for_one_tiered, not "
        "the per-hour rate path — caller must pass hourly_net_load_kwh"
    )


def _apply_nem_one_for_one_tiered(
    *,
    hourly_net_load_kwh: list[float],
    tariff: TariffSchedule,
) -> ExportCreditResult:
    """NEM 1:1 retail-rate netting on a tiered tariff.

    Aggregates each month's imports and exports, then bills the tier
    table on imports-only and on ``max(0, imports − exports)``. The
    credit per month is the bill delta. Surplus exports beyond
    same-month imports forfeit (NSC year-end monetization is the
    caller's concern).
    """
    _validate_hourly(hourly_net_load_kwh, name="hourly_net_load_kwh")
    if tariff.structure != "tiered":
        raise ValueError(
            f"_apply_nem_one_for_one_tiered expects structure='tiered' (got {tariff.structure!r})"
        )
    sorted_blocks = sort_tiered_blocks(tariff)

    monthly_imports = [0.0] * 12
    monthly_exports = [0.0] * 12
    for hour_index, net in enumerate(hourly_net_load_kwh):
        month_idx = _TMY_CALENDAR[hour_index][0] - 1
        if net > 0.0:
            monthly_imports[month_idx] += net
        elif net < 0.0:
            monthly_exports[month_idx] += -net

    monthly_credit: list[float] = []
    annual_kwh_credited = 0.0
    for month_idx in range(12):
        imports = monthly_imports[month_idx]
        exports = monthly_exports[month_idx]
        netted = max(0.0, imports - exports)
        bill_imports = walk_tier_charge(imports, sorted_blocks)
        bill_netted = walk_tier_charge(netted, sorted_blocks)
        monthly_credit.append(bill_imports - bill_netted)
        # Only the slice of exports that offset same-month imports
        # counts as "credited"; surplus forfeits at month-end.
        annual_kwh_credited += min(exports, imports)

    return ExportCreditResult(
        regime="nem_one_for_one",
        monthly_credit=monthly_credit,
        annual_credit=sum(monthly_credit),
        annual_kwh_exported=annual_kwh_credited,
    )


def apply_nem_one_for_one(
    *,
    hourly_export_kwh: list[float],
    tariff: TariffSchedule,
    hourly_net_load_kwh: list[float] | None = None,
) -> ExportCreditResult:
    """NEM 1:1 retail-rate net metering.

    For **flat / TOU** tariffs: each exported kWh credits at the tariff
    rate that would have applied had the same kWh been imported in that
    hour. ``hourly_net_load_kwh`` is unused and may be omitted.

    For **tiered** tariffs: requires ``hourly_net_load_kwh`` (signed —
    positive = import, negative = export). The helper aggregates each
    month's imports and exports separately and walks the tier table on
    both ``imports-only`` and ``max(0, imports − exports)``; the credit
    is the bill delta. This produces the correct PG&E-E1-style behavior
    rather than crediting at the top-tier rate (a conservative upper
    bound that overstated savings on net-importer households).
    """
    _validate_hourly(hourly_export_kwh, name="hourly_export_kwh")

    if tariff.structure == "tiered":
        if hourly_net_load_kwh is None:
            raise ValueError(
                "NEM 1:1 with a tiered tariff requires hourly_net_load_kwh "
                "(signed: positive=import, negative=export) — tier-walking "
                "netting can't be derived from exports alone"
            )
        return _apply_nem_one_for_one_tiered(
            hourly_net_load_kwh=hourly_net_load_kwh,
            tariff=tariff,
        )

    monthly = [0.0] * 12
    total_kwh = 0.0
    for hour_index, export_kwh in enumerate(hourly_export_kwh):
        kwh = max(0.0, export_kwh)
        if kwh == 0.0:
            continue
        month, is_weekday, hour_of_day = _TMY_CALENDAR[hour_index]
        rate = _resolve_nem_one_rate_flat_or_tou(
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
    config: ExportCreditConfig,
    hourly_export_kwh: list[float],
    tariff: TariffSchedule | None = None,
    hourly_net_load_kwh: list[float] | None = None,
) -> ExportCreditResult:
    """Single dispatch entry point for the four export-credit regimes.

    Delegates to ``config.apply(...)``; each variant carries its own
    apply method so this function is pure routing. Validation of
    regime/field consistency happens at parse time inside Pydantic.

    ``hourly_net_load_kwh`` (signed: positive = import, negative = export)
    is required only for **NEM 1:1 with a tiered tariff** — the
    tier-walking netting can't be derived from exports alone. Other
    regime/structure pairs ignore it.
    """
    return config.apply(
        hourly_export_kwh=hourly_export_kwh,
        tariff=tariff,
        hourly_net_load_kwh=hourly_net_load_kwh,
    )


# Re-exported here so callers can grab the union from one place. The
# variant classes themselves live in ``backend.engine.inputs`` because
# they are part of the IO boundary — putting them here would create
# an import cycle (engine.steps.* eagerly load each step module, which
# would re-enter inputs.py).
from backend.engine.inputs import (  # noqa: E402
    ExportCreditConfig,
    NbtConfig,
    NemOneForOneConfig,
    SegFlatConfig,
    SegTouConfig,
)

__all__ = [
    "ExportCreditConfig",
    "ExportCreditResult",
    "NbtConfig",
    "NemOneForOneConfig",
    "SegFlatConfig",
    "SegTouConfig",
    "apply_export_credit",
    "apply_nem_one_for_one",
    "apply_nem_three_nbt",
    "apply_seg_flat",
    "apply_seg_tou",
]

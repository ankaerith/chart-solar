"""8760-hour rule-based battery dispatch.

Phase 1a covers two strategies:

* ``self_consumption`` — soak up every kWh of would-be export, then
  discharge whenever the household imports. Tariff-agnostic; the
  default for solar-plus-storage installs without TOU rates.
* ``tou_arbitrage`` — charge during off-peak hours, discharge during
  on-peak. Inferred peak/off-peak windows come from the active
  :class:`backend.providers.tariff.TouPeriod` list. Non-TOU schedules
  silently fall back to ``self_consumption``.

Each path produces hourly arrays the BatteryDispatch chart consumes
directly: SOC, charge / discharge per hour, and the post-battery
grid import / export streams. Round-trip efficiency is applied on the
discharge side so the SOC math stays a clean energy-balance accumulator
(charged kWh land in the bank at face value; discharged kWh exit
multiplied by ``rte``).

LP-optimised dispatch is deferred (PRODUCT_PLAN open items); rule-based
is what powers the v1 chart, and the abstraction is small enough that
swapping in an LP solver later doesn't change the public surface.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from backend.engine.inputs import BatteryInputs, DispatchStrategy
from backend.engine.registry import register
from backend.providers.irradiance import HOURS_PER_TMY, tmy_hour_calendar
from backend.providers.tariff import TariffSchedule, TouPeriod, first_matching_tou_period


class BatteryDispatchResult(BaseModel):
    """Hour-by-hour outcome of the dispatch simulation. Every array is
    exactly 8760 long, hour-aligned with the upstream net-load shape.

    ``hourly_grid_import_kwh`` / ``hourly_grid_export_kwh`` are the
    *post-battery* streams — what hits the meter after dispatch. Sum
    them for annual totals; their difference matches the no-battery
    net load only when the dispatch strategy didn't intervene that
    hour (battery already full or empty).
    """

    strategy: DispatchStrategy
    hourly_charge_kwh: list[float] = Field(
        ...,
        min_length=HOURS_PER_TMY,
        max_length=HOURS_PER_TMY,
    )
    hourly_discharge_kwh: list[float] = Field(
        ...,
        min_length=HOURS_PER_TMY,
        max_length=HOURS_PER_TMY,
    )
    hourly_soc_kwh: list[float] = Field(
        ...,
        min_length=HOURS_PER_TMY,
        max_length=HOURS_PER_TMY,
    )
    hourly_grid_import_kwh: list[float] = Field(
        ...,
        min_length=HOURS_PER_TMY,
        max_length=HOURS_PER_TMY,
    )
    hourly_grid_export_kwh: list[float] = Field(
        ...,
        min_length=HOURS_PER_TMY,
        max_length=HOURS_PER_TMY,
    )

    @property
    def annual_charged_kwh(self) -> float:
        return sum(self.hourly_charge_kwh)

    @property
    def annual_discharged_kwh(self) -> float:
        return sum(self.hourly_discharge_kwh)

    @property
    def annual_grid_import_kwh(self) -> float:
        return sum(self.hourly_grid_import_kwh)

    @property
    def annual_grid_export_kwh(self) -> float:
        return sum(self.hourly_grid_export_kwh)


@register("engine.battery_dispatch")
def dispatch_battery(
    *,
    battery: BatteryInputs,
    hourly_net_load_kwh: list[float],
    tariff: TariffSchedule | None = None,
) -> BatteryDispatchResult:
    """Simulate hour-by-hour battery operation.

    ``hourly_net_load_kwh`` is the pre-battery grid load: positive means
    the household imports that hour, negative means solar exports.

    The function is pure: no IO, no module-level state mutated. Walks
    the 8760 hours linearly so a Monte Carlo wrapper can call it
    thousands of times without warm-up cost.
    """
    if len(hourly_net_load_kwh) != HOURS_PER_TMY:
        raise ValueError(
            f"hourly_net_load_kwh must have {HOURS_PER_TMY} entries; got {len(hourly_net_load_kwh)}"
        )

    strategy = _resolve_strategy(battery.strategy, tariff)
    if strategy == "tou_arbitrage":
        # _resolve_strategy guarantees a non-empty TOU schedule on this branch.
        assert tariff is not None and tariff.tou_periods is not None
        is_peak_per_hour: list[bool] | None = _build_peak_mask(tariff.tou_periods)
    else:
        is_peak_per_hour = None

    usable_capacity = battery.capacity_kwh * battery.usable_pct
    floor_kwh = usable_capacity * battery.reserve_pct
    rte = battery.round_trip_efficiency
    # Round-trip loss is applied on the discharge side so the SOC line
    # reads as "energy in the bank" rather than "energy the inverter
    # could deliver right now."
    discharge_efficiency = rte
    max_charge = battery.max_charge_kw
    max_discharge = battery.max_discharge_kw

    hourly_charge: list[float] = [0.0] * HOURS_PER_TMY
    hourly_discharge: list[float] = [0.0] * HOURS_PER_TMY
    hourly_soc: list[float] = [0.0] * HOURS_PER_TMY
    hourly_import: list[float] = [0.0] * HOURS_PER_TMY
    hourly_export: list[float] = [0.0] * HOURS_PER_TMY

    soc = floor_kwh
    for hour, net_load in enumerate(hourly_net_load_kwh):
        net_import = max(0.0, net_load)
        net_export = max(0.0, -net_load)

        charge = 0.0
        discharge = 0.0
        grid_charge = 0.0  # kWh of charge sourced from grid (TOU only)

        if strategy == "self_consumption":
            if net_export > 0.0:
                headroom = usable_capacity - soc
                charge = min(net_export, max_charge, headroom)
            if net_import > 0.0:
                available_kwh = max(0.0, soc - floor_kwh) * discharge_efficiency
                discharge = min(net_import, max_discharge, available_kwh)
        else:
            assert is_peak_per_hour is not None
            on_peak = is_peak_per_hour[hour]
            if not on_peak:
                headroom = usable_capacity - soc
                if net_export > 0.0:
                    charge = min(net_export, max_charge, headroom)
                else:
                    # Charge from grid up to the C-rate cap. The
                    # arbitrage thesis: pay off-peak rate now to avoid
                    # peak rate later.
                    grid_charge = min(max_charge, headroom)
                    charge = grid_charge
            elif net_import > 0.0:
                available_kwh = max(0.0, soc - floor_kwh) * discharge_efficiency
                discharge = min(net_import, max_discharge, available_kwh)

        soc += charge
        if discharge > 0.0:
            soc -= discharge / discharge_efficiency
        if soc < floor_kwh:
            soc = floor_kwh
        elif soc > usable_capacity:
            soc = usable_capacity

        post_import = net_import - discharge + grid_charge
        post_export = net_export - min(charge - grid_charge, net_export)

        hourly_charge[hour] = charge
        hourly_discharge[hour] = discharge
        hourly_soc[hour] = soc
        hourly_import[hour] = max(0.0, post_import)
        hourly_export[hour] = max(0.0, post_export)

    return BatteryDispatchResult(
        strategy=strategy,
        hourly_charge_kwh=hourly_charge,
        hourly_discharge_kwh=hourly_discharge,
        hourly_soc_kwh=hourly_soc,
        hourly_grid_import_kwh=hourly_import,
        hourly_grid_export_kwh=hourly_export,
    )


def _resolve_strategy(
    requested: DispatchStrategy,
    tariff: TariffSchedule | None,
) -> DispatchStrategy:
    """Promote ``tou_arbitrage`` to ``self_consumption`` when the active
    schedule isn't TOU-shaped. Self-consumption still produces useful
    dispatch on a flat or tiered tariff."""
    if requested != "tou_arbitrage":
        return requested
    if tariff is None or tariff.tou_periods is None or not tariff.tou_periods:
        return "self_consumption"
    return "tou_arbitrage"


def _build_peak_mask(periods: list[TouPeriod]) -> list[bool]:
    """Mark each of the 8760 hours as on-peak or off-peak.

    Peak rate is the maximum ``rate_per_kwh`` across all periods; a
    given hour is peak when the matching period's rate equals that
    maximum. Hours with no matching period (rare; tariff-authoring
    bug) default to off-peak so dispatch degrades to "store solar
    surplus" rather than crash.

    Memoises across the 8760 hours: only 12 × 2 × 24 = 576 distinct
    ``(month, is_weekday, hour_of_day)`` cells exist, so a Monte
    Carlo wrapper that calls ``dispatch_battery`` thousands of times
    avoids 8760 × periods scans on every path.
    """
    if not periods:
        return [False] * HOURS_PER_TMY
    peak_rate = max(period.rate_per_kwh for period in periods)
    if math.isclose(peak_rate, 0.0):
        return [False] * HOURS_PER_TMY

    cell_cache: dict[tuple[int, bool, int], bool] = {}
    mask: list[bool] = []
    for month, is_weekday, hour_of_day in tmy_hour_calendar():
        cell = (month, is_weekday, hour_of_day)
        cached = cell_cache.get(cell)
        if cached is None:
            match = first_matching_tou_period(
                periods,
                month=month,
                is_weekday=is_weekday,
                hour_of_day=hour_of_day,
            )
            cached = match is not None and math.isclose(match.rate_per_kwh, peak_rate)
            cell_cache[cell] = cached
        mask.append(cached)
    return mask


__all__ = [
    "BatteryDispatchResult",
    "dispatch_battery",
]

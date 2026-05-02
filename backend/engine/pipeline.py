"""Engine pipeline.

Composes the step registry into an end-to-end forecast. Steps are
registered under ``engine.<step>`` feature keys (see
``backend.engine.registry``); the canonical ordering lives in
``ENGINE_STEP_ORDER`` and the pipeline walks it, dispatching each
registered step through a per-step adapter that extracts the step's
arguments from ``ForecastState`` and writes the step's output back
under the matching artifact key.

ADR 0006 reshapes the order: cell-temperature derating and inverter
clipping are baked into ``engine.dc_production`` (pvlib's ModelChain),
so they don't appear here as separate steps. ``engine.snow`` runs
after dc_production and consumes its hourly POA + the TMY's monthly
snowfall / RH to layer Townsend snow loss onto the AC stream;
``engine.soiling`` is still deferred (pvlib's HSU model needs PM2.5 /
PM10 columns the irradiance providers don't yet carry).

The pipeline is sync-only: TMY fetching is the worker's responsibility
(network IO, async). Tests pass a ``synthetic_tmy()`` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.domain.tmy import HOURS_PER_TMY, TmyData
from backend.engine.inputs import ConsumptionInputs, ForecastInputs
from backend.engine.registry import StepFn, steps_for
from backend.engine.snapshot import build_snapshot
from backend.engine.steps.battery_dispatch import BatteryDispatchResult
from backend.engine.steps.dc_production import DcProductionResult
from backend.engine.steps.snow import SnowLossResult

#: Canonical execution order. Pipeline iterates this list, skipping any
#: key that is either unregistered or absent from the caller's requested
#: feature set. Adding a step here is a contract change — update tier
#: configs and regression fixtures alongside.
ENGINE_STEP_ORDER: tuple[str, ...] = (
    "engine.irradiance",
    "engine.consumption",
    "engine.dc_production",
    "engine.snow",
    "engine.degradation",
    "engine.battery_dispatch",
    "engine.tariff",
    "engine.export_credit",
    "engine.finance",
)


@dataclass
class ForecastState:
    inputs: ForecastInputs
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastResult:
    inputs: ForecastInputs
    artifacts: dict[str, Any]


_StepAdapter = Callable[[ForecastState, StepFn], None]


def run_forecast(
    inputs: ForecastInputs,
    *,
    tmy: TmyData,
    feature_keys: set[str] | None = None,
) -> ForecastResult:
    """Execute the engine pipeline against pre-fetched weather.

    ``tmy`` is required: the engine never calls a network provider
    itself. The forecast worker (``backend.workers.forecast_worker``)
    or any direct caller is responsible for fetching the TMY before
    invoking this function. Tests pass ``backend.providers.fake.synthetic_tmy(...)``.

    ``feature_keys`` selects which steps to run; default is the full
    canonical order. A key absent from the registry (e.g.
    ``engine.consumption`` before its step lands) is skipped silently —
    the pipeline degrades rather than raising, so partial Phase 1a
    deployments still produce results.

    Artifacts are keyed by feature key so downstream consumers can
    address a step's output without knowing the pipeline's internal
    composition.
    """
    state = ForecastState(inputs=inputs)
    state.artifacts["engine.irradiance"] = tmy
    state.artifacts["engine.consumption"] = _resolve_consumption(inputs.consumption)
    # Snapshot before steps run: every saved forecast carries an
    # engine_version + pvlib_version + canonical hash of its inputs +
    # tariff so the methodology export can prove what produced this
    # result, and a re-open can detect "tariff changed since you saved
    # this" without re-running the pipeline.
    state.artifacts["engine.snapshot"] = build_snapshot(
        inputs=inputs,
        tariff=inputs.tariff.schedule,
        irradiance_source=tmy.source,
        irradiance_fetched_at=tmy.fetched_at,
    )

    requested = set(ENGINE_STEP_ORDER) if feature_keys is None else feature_keys
    registered = {step.feature_key: step.fn for step in steps_for(requested)}

    for key in ENGINE_STEP_ORDER:
        if key not in requested:
            continue
        adapter = _ADAPTERS.get(key)
        if adapter is None:
            # Step has no registry-driven adapter (e.g. irradiance /
            # consumption are pre-populated above). Nothing to do.
            continue
        if key not in registered:
            # Adapter exists but no @register — step is in-flight.
            continue
        adapter(state, registered[key])

    return ForecastResult(inputs=state.inputs, artifacts=state.artifacts)


def _resolve_consumption(c: ConsumptionInputs | None) -> list[float]:
    """Pick the right hourly consumption shape from the input options.

    A full ``hourly_kwh`` wins when present; otherwise the annual total
    is spread evenly across the 8760 hours; otherwise the household has
    zero load (a degenerate but useful baseline — every produced kWh
    becomes export, which exercises the export-credit chain).
    """
    if c is None:
        return [0.0] * HOURS_PER_TMY
    if c.hourly_kwh is not None:
        return c.hourly_kwh
    if c.annual_kwh is not None:
        even = c.annual_kwh / HOURS_PER_TMY
        return [even] * HOURS_PER_TMY
    return [0.0] * HOURS_PER_TMY


def _production_kw(state: ForecastState) -> list[float]:
    """Hourly AC production stream after the snow derate, when present.

    ``engine.snow`` runs between ``engine.dc_production`` and the load /
    billing steps, so when the snow artifact exists every downstream
    consumer (battery dispatch, tariff, export credit, finance) reads
    the post-snow stream — same as if pvlib's ModelChain had produced
    it directly. With no snow step (TMY without snow + RH columns), we
    fall back to the raw dc_production stream.
    """
    snow: SnowLossResult | None = state.artifacts.get("engine.snow")
    if snow is not None:
        return snow.adjusted_hourly_ac_kw
    dc: DcProductionResult = state.artifacts["engine.dc_production"]
    return dc.hourly_ac_kw


def _net_load(state: ForecastState) -> list[float]:
    """Hourly grid net-load: positive = import, negative = export.

    When ``engine.battery_dispatch`` has produced post-battery
    streams, this returns the *post-battery* signed net load
    (``import − export``) so the tariff + export-credit steps bill
    against what actually hits the meter. Pre-battery shape — pure
    ``consumption − production`` — when no battery dispatch ran. The
    production term comes from ``_production_kw``, so snow derate (if
    any) is already baked in.
    """
    battery: BatteryDispatchResult | None = state.artifacts.get("engine.battery_dispatch")
    if battery is not None:
        return [
            imp - exp
            for imp, exp in zip(
                battery.hourly_grid_import_kwh,
                battery.hourly_grid_export_kwh,
                strict=True,
            )
        ]
    consumption: list[float] = state.artifacts["engine.consumption"]
    return [c - p for c, p in zip(consumption, _production_kw(state), strict=True)]


def _adapter_dc_production(state: ForecastState, fn: StepFn) -> None:
    tmy: TmyData = state.artifacts["engine.irradiance"]
    state.artifacts["engine.dc_production"] = fn(system=state.inputs.system, tmy=tmy)


def _adapter_snow(state: ForecastState, fn: StepFn) -> None:
    tmy: TmyData = state.artifacts["engine.irradiance"]
    dc: DcProductionResult = state.artifacts["engine.dc_production"]
    result = fn(tmy=tmy, system=state.inputs.system, dc=dc)
    if result is not None:
        state.artifacts["engine.snow"] = result


def _adapter_degradation(state: ForecastState, fn: StepFn) -> None:
    state.artifacts["engine.degradation"] = fn(years=state.inputs.financial.hold_years)


def _adapter_battery_dispatch(state: ForecastState, fn: StepFn) -> None:
    # Battery is opt-in: skip silently when no BatteryInputs supplied
    # so existing forecasts (no battery configured) keep their shape.
    battery = state.inputs.battery
    if battery is None:
        return
    state.artifacts["engine.battery_dispatch"] = fn(
        battery=battery,
        hourly_net_load_kwh=_net_load(state),
        tariff=state.inputs.tariff.schedule,
    )


def _adapter_tariff(state: ForecastState, fn: StepFn) -> None:
    schedule = state.inputs.tariff.schedule
    if schedule is None:
        return
    state.artifacts["engine.tariff"] = fn(
        hourly_net_load_kwh=_net_load(state),
        tariff=schedule,
    )


def _adapter_export_credit(state: ForecastState, fn: StepFn) -> None:
    config = state.inputs.tariff.export_credit
    if config is None:
        return
    net_load = _net_load(state)
    hourly_export = [max(0.0, -nl) for nl in net_load]
    state.artifacts["engine.export_credit"] = fn(
        config=config,
        hourly_export_kwh=hourly_export,
        tariff=state.inputs.tariff.schedule,
        hourly_net_load_kwh=net_load,
    )


def _adapter_finance(state: ForecastState, fn: StepFn) -> None:
    # Finance composes upstream artifacts; missing prerequisites mean
    # the orchestrator can't produce a meaningful answer, so we skip
    # silently — same degradation pattern as tariff/export_credit.
    if state.inputs.financial.system_cost is None:
        return
    if state.inputs.tariff.schedule is None:
        return
    if "engine.dc_production" not in state.artifacts:
        return
    if "engine.degradation" not in state.artifacts:
        return
    dc: DcProductionResult = state.artifacts["engine.dc_production"]
    snow: SnowLossResult | None = state.artifacts.get("engine.snow")
    if snow is not None:
        # Finance re-bills hourly + tracks annual energy per year, so
        # both streams need the snow derate baked in. The dc_production
        # struct's other fields (peak_ac_kw, ratios, POA) are unaffected
        # by snow and pass through unchanged.
        dc = dc.model_copy(
            update={
                "hourly_ac_kw": snow.adjusted_hourly_ac_kw,
                "annual_ac_kwh": snow.adjusted_annual_ac_kwh,
            }
        )
    state.artifacts["engine.finance"] = fn(
        financial=state.inputs.financial,
        consumption=state.artifacts["engine.consumption"],
        dc=dc,
        degradation=state.artifacts["engine.degradation"],
        schedule=state.inputs.tariff.schedule,
        export_credit=state.inputs.tariff.export_credit,
    )


_ADAPTERS: dict[str, _StepAdapter] = {
    "engine.dc_production": _adapter_dc_production,
    "engine.snow": _adapter_snow,
    "engine.degradation": _adapter_degradation,
    "engine.battery_dispatch": _adapter_battery_dispatch,
    "engine.tariff": _adapter_tariff,
    "engine.export_credit": _adapter_export_credit,
    "engine.finance": _adapter_finance,
}

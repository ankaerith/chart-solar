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
so they don't appear here as separate steps. Soiling and snow remain
pipeline-aware but are deferred until the irradiance providers carry
monthly precipitation / snowfall / RH — they're absent from
``ENGINE_STEP_ORDER`` rather than registered no-ops.

The pipeline is sync-only: TMY fetching is the worker's responsibility
(network IO, async). Tests pass a ``synthetic_tmy()`` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.engine.inputs import ConsumptionInputs, ForecastInputs
from backend.engine.registry import StepFn, steps_for
from backend.engine.steps.dc_production import DcProductionResult
from backend.providers.irradiance import HOURS_PER_TMY, TmyData

#: Canonical execution order. Pipeline iterates this list, skipping any
#: key that is either unregistered (e.g. ``engine.finance`` until its
#: orchestrator lands) or absent from the caller's requested feature
#: set. Adding a step here is a contract change — update tier configs
#: and regression fixtures alongside.
ENGINE_STEP_ORDER: tuple[str, ...] = (
    "engine.irradiance",
    "engine.consumption",
    "engine.dc_production",
    "engine.degradation",
    "engine.tariff",
    "engine.export_credit",
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
    composition. Intermediate derived series (net load, hourly export)
    are stored under ``engine.net_load`` / ``engine.hourly_export_kwh``
    so the tariff and export-credit adapters share work.
    """
    state = ForecastState(inputs=inputs)
    state.artifacts["engine.irradiance"] = tmy
    state.artifacts["engine.consumption"] = _resolve_consumption(inputs.consumption)

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
        return list(c.hourly_kwh)
    if c.annual_kwh is not None:
        even = c.annual_kwh / HOURS_PER_TMY
        return [even] * HOURS_PER_TMY
    return [0.0] * HOURS_PER_TMY


def _adapter_dc_production(state: ForecastState, fn: StepFn) -> None:
    tmy: TmyData = state.artifacts["engine.irradiance"]
    state.artifacts["engine.dc_production"] = fn(system=state.inputs.system, tmy=tmy)


def _adapter_degradation(state: ForecastState, fn: StepFn) -> None:
    state.artifacts["engine.degradation"] = fn(years=state.inputs.financial.hold_years)


def _ensure_net_load(state: ForecastState) -> list[float]:
    """Compute net load (consumption − AC production) once and cache it.

    Both ``engine.tariff`` and ``engine.export_credit`` need this same
    array; computing it here keeps the per-adapter code linear and
    side-effect-free aside from the cache write.
    """
    cached = state.artifacts.get("engine.net_load")
    if cached is not None:
        return list(cached)
    consumption: list[float] = state.artifacts["engine.consumption"]
    dc: DcProductionResult = state.artifacts["engine.dc_production"]
    net_load = [c - p for c, p in zip(consumption, dc.hourly_ac_kw, strict=True)]
    state.artifacts["engine.net_load"] = net_load
    return net_load


def _adapter_tariff(state: ForecastState, fn: StepFn) -> None:
    schedule = state.inputs.tariff.schedule
    if schedule is None:
        return
    net_load = _ensure_net_load(state)
    state.artifacts["engine.tariff"] = fn(
        hourly_net_load_kwh=net_load,
        tariff=schedule,
    )


def _adapter_export_credit(state: ForecastState, fn: StepFn) -> None:
    config = state.inputs.tariff.export_credit
    if config is None:
        return
    net_load = _ensure_net_load(state)
    hourly_export = [max(0.0, -nl) for nl in net_load]
    state.artifacts["engine.hourly_export_kwh"] = hourly_export
    state.artifacts["engine.export_credit"] = fn(
        regime=config.regime,
        hourly_export_kwh=hourly_export,
        tariff=state.inputs.tariff.schedule,
        hourly_avoided_cost_per_kwh=config.hourly_avoided_cost_per_kwh,
        rate_per_kwh=config.flat_rate_per_kwh,
        hourly_rate_per_kwh=config.hourly_rate_per_kwh,
    )


_ADAPTERS: dict[str, _StepAdapter] = {
    "engine.dc_production": _adapter_dc_production,
    "engine.degradation": _adapter_degradation,
    "engine.tariff": _adapter_tariff,
    "engine.export_credit": _adapter_export_credit,
}

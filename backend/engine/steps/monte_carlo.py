"""Monte Carlo wrapper.

Phase 1a: stochastic axes — rate-escalation path × weather year × degradation
× hold duration. Output is a distribution (P10/P50/P90 fan), never a point
estimate. Sample count and which axes are sampled are configurable.

Architecturally this is a *wrapper* around the finance step, not a registry
step in its own right: the pipeline orchestrator builds one baseline
``ForecastState`` (including the expensive pvlib ModelChain run), then this
module replays just the cheap downstream math (degradation curve + per-year
re-billing + cashflow roll-up) under perturbed inputs. ``engine.dc_production``
deliberately is *not* re-run per path — sampling weather variability via a
scalar multiplier on annual production keeps a 500-path Monte Carlo inside
the 60s budget on a Fly small machine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field

from backend.engine.steps.dc_production import DcProductionResult
from backend.engine.steps.degradation import (
    DEFAULT_ANNUAL_LOSS,
    DEFAULT_FIRST_YEAR_LOSS,
    degradation_factors,
)
from backend.engine.steps.finance import run_finance

if TYPE_CHECKING:
    # ``ForecastState`` lives in ``backend.engine.pipeline``; importing it
    # at runtime would cycle (pipeline ← steps ← monte_carlo ← pipeline).
    # The wrapper only ever touches ``state.inputs`` / ``state.artifacts``,
    # so duck typing at runtime is safe.
    from backend.engine.pipeline import ForecastState

#: Schema bounds on FinancialInputs.rate_escalation. Sampled values are
#: clamped here so a wide-tailed normal draw can't exit the validator's
#: range and crash a path.
_RATE_ESCALATION_BOUNDS = (-0.10, 0.20)

#: Practical upper bound on annual degradation. Field studies put even
#: poorly-installed strings well under 2 %/yr; we clamp to 5 % to avoid
#: a tail draw that drives capacity factor negative inside hold_years.
_ANNUAL_LOSS_CAP = 0.05


class MonteCarloSampling(BaseModel):
    """Per-axis sampling parameters.

    Defaults reflect the Phase-1a literature:

    * Rate-escalation σ ≈ 1 percentage point captures inter-utility
      variability without overpowering the deterministic mean.
    * Annual-loss σ ≈ 0.1 percentage point matches NREL's reported
      spread for crystalline-Si installs around the 0.55 %/yr median.
    * Weather scale σ ≈ 7 % matches the NSRDB-vs-actual-year spread
      observed for residential rooftops in CONUS.
    * Hold-years jitter defaults to zero — most users have a definite
      hold horizon and a uniform jitter would dilute their input.
    """

    rate_escalation_std: float = Field(0.01, ge=0.0)
    annual_loss_std: float = Field(0.001, ge=0.0)
    annual_loss_min: float = Field(0.001, ge=0.0)
    weather_scale_std: float = Field(0.07, ge=0.0)
    weather_scale_min: float = Field(0.5, ge=0.0)
    hold_years_jitter: int = Field(0, ge=0)


class MonteCarloPercentiles(BaseModel):
    """P10 / P50 / P90 of one sampled metric across all paths."""

    p10: float
    p50: float
    p90: float


class MonteCarloResult(BaseModel):
    """Distribution + raw paths for downstream charts.

    ``cumulative_net_wealth`` is the per-year fan-chart series — entry
    ``t`` is the P10/P50/P90 of the cumulative cashflow at year ``t``
    across every sampled path. Year 0 is the homeowner's initial outlay
    (always negative on a cash buy), year ``hold_years`` is the
    project's terminal wealth.

    ``npv_paths`` and ``cumulative_paths`` keep the raw per-path arrays
    so downstream tornado / scenario-overlay UI can re-aggregate without
    re-running the wrapper. Paths shorter than the longest are tail-
    padded with their final value (post-payoff steady state).
    """

    n: int
    seed: int
    sampling: MonteCarloSampling
    npv: MonteCarloPercentiles
    payback_years: MonteCarloPercentiles | None
    cumulative_net_wealth: list[MonteCarloPercentiles]
    npv_paths: list[float]
    cumulative_paths: list[list[float]]
    failed_paths: int


def _scaled_dc(dc: DcProductionResult, scale: float) -> DcProductionResult:
    """Uniform multiplier on every hour + roll-up totals.

    Modeling weather variability as a scalar is the cheap-but-defensible
    proxy for resampling a different TMY year — both shift annual
    production by a multiplicative factor. The audit's tornado plot
    surfaces this assumption to the user. ``inverter_ac_kw`` and
    ``dc_ac_ratio`` are nameplate facts about the system, not weather-
    dependent, so they pass through untouched.
    """
    return dc.model_copy(
        update={
            "hourly_dc_kw": [h * scale for h in dc.hourly_dc_kw],
            "hourly_ac_kw": [h * scale for h in dc.hourly_ac_kw],
            "annual_dc_kwh": dc.annual_dc_kwh * scale,
            "annual_ac_kwh": dc.annual_ac_kwh * scale,
            "peak_ac_kw": dc.peak_ac_kw * scale,
        }
    )


#: P10 / P50 / P90 in one numpy call. Pulled out as a constant so every
#: percentile reduction in this module keeps the same anchor points; the
#: fan-chart UI assumes these three.
_PERCENTILES: tuple[int, int, int] = (10, 50, 90)


def _percentiles(values: list[float]) -> MonteCarloPercentiles:
    p10, p50, p90 = np.percentile(np.asarray(values), _PERCENTILES)
    return MonteCarloPercentiles(p10=float(p10), p50=float(p50), p90=float(p90))


def _aligned_cumulative(paths: list[list[float]]) -> np.ndarray:
    """Pad shorter paths with their final value so the fan chart is rectangular.

    Paths can differ in length when ``hold_years_jitter`` is non-zero;
    once a path's hold ends, the homeowner's wealth-versus-no-solar
    counterfactual stops accumulating. Holding the terminal value is
    the conservative choice for a fan chart.
    """
    horizon = max(len(p) for p in paths)
    padded = [p + [p[-1]] * (horizon - len(p)) for p in paths]
    return np.asarray(padded)


def run_monte_carlo(
    state: ForecastState,
    n: int,
    *,
    seed: int = 0,
    sampling: MonteCarloSampling | None = None,
) -> MonteCarloResult:
    """Sample ``n`` perturbed forecasts and reduce to a distribution.

    ``state`` must already carry a baseline ``engine.dc_production`` and
    ``engine.consumption`` (in practice: run ``run_forecast`` first; the
    forecast worker does this). The wrapper mutates nothing on the input
    state — every path builds its own ``DcProductionResult`` /
    ``DegradationCurve`` and discards them after rolling up.

    ``seed`` is honoured deterministically: same seed → same paths.
    Tests rely on this for golden-fixture stability; the API surface
    exposes it so the worker can persist the seed alongside the
    artifact for reproducibility.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    inputs = state.inputs
    if inputs.financial.system_cost is None:
        raise ValueError("system_cost is required for Monte Carlo")
    if inputs.tariff.schedule is None:
        raise ValueError("tariff.schedule is required for Monte Carlo")
    dc = state.artifacts.get("engine.dc_production")
    if not isinstance(dc, DcProductionResult):
        raise ValueError("Monte Carlo requires engine.dc_production in state.artifacts")
    consumption = state.artifacts.get("engine.consumption")
    if not isinstance(consumption, list):
        raise ValueError("Monte Carlo requires engine.consumption in state.artifacts")

    sampling = sampling or MonteCarloSampling()
    rng = np.random.default_rng(seed)
    base_financial = inputs.financial

    npv_paths: list[float] = []
    cumulative_paths: list[list[float]] = []
    payback_paths: list[float] = []
    failed = 0

    for _ in range(n):
        weather_scale = max(
            sampling.weather_scale_min,
            float(rng.normal(1.0, sampling.weather_scale_std)),
        )
        rate_escalation = max(
            _RATE_ESCALATION_BOUNDS[0],
            min(
                _RATE_ESCALATION_BOUNDS[1],
                float(rng.normal(base_financial.rate_escalation, sampling.rate_escalation_std)),
            ),
        )
        annual_loss = min(
            _ANNUAL_LOSS_CAP,
            max(
                sampling.annual_loss_min,
                float(rng.normal(DEFAULT_ANNUAL_LOSS, sampling.annual_loss_std)),
            ),
        )
        if sampling.hold_years_jitter > 0:
            jitter = int(rng.integers(-sampling.hold_years_jitter, sampling.hold_years_jitter + 1))
            hold_years = max(1, base_financial.hold_years + jitter)
        else:
            hold_years = base_financial.hold_years

        path_financial = base_financial.model_copy(
            update={"rate_escalation": rate_escalation, "hold_years": hold_years}
        )
        path_dc = _scaled_dc(dc, weather_scale)
        path_curve = degradation_factors(
            years=hold_years,
            first_year_loss=DEFAULT_FIRST_YEAR_LOSS,
            annual_loss=annual_loss,
        )

        try:
            result = run_finance(
                financial=path_financial,
                consumption=consumption,
                dc=path_dc,
                degradation=path_curve,
                schedule=inputs.tariff.schedule,
                export_credit=inputs.tariff.export_credit,
            )
        except (ValueError, ArithmeticError):
            # A pathological draw (e.g. zero-baseline-bill household with
            # extreme degradation) can land outside the finance step's
            # preconditions. We log the drop count so the caller can
            # decide whether the survival rate is acceptable, but a
            # single bad path doesn't kill the whole run.
            failed += 1
            continue

        npv_paths.append(result.npv)
        cumulative_paths.append(np.cumsum(result.per_year_cashflow).tolist())
        if result.discounted_payback_years is not None:
            payback_paths.append(result.discounted_payback_years)

    if not npv_paths:
        raise RuntimeError(f"every Monte Carlo path failed ({failed}/{n})")

    cum_arr = _aligned_cumulative(cumulative_paths)
    # Single percentile call per year (axis=0 reduces across paths) — three
    # rows out, one per anchor point in _PERCENTILES.
    cum_pct = np.percentile(cum_arr, _PERCENTILES, axis=0)
    cumulative_pct = [
        MonteCarloPercentiles(
            p10=float(cum_pct[0, t]), p50=float(cum_pct[1, t]), p90=float(cum_pct[2, t])
        )
        for t in range(cum_arr.shape[1])
    ]

    return MonteCarloResult(
        n=n,
        seed=seed,
        sampling=sampling,
        npv=_percentiles(npv_paths),
        payback_years=_percentiles(payback_paths) if payback_paths else None,
        cumulative_net_wealth=cumulative_pct,
        npv_paths=npv_paths,
        cumulative_paths=cumulative_paths,
        failed_paths=failed,
    )

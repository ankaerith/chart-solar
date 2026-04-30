"""Tornado sensitivity wrapper.

One-axis-at-a-time perturbation of the headline NPV, sorted by
absolute swing. Sibling of :mod:`backend.engine.steps.monte_carlo` —
both replay the cheap downstream finance math against perturbed
inputs without re-running the expensive ModelChain.

Each row in the result tells the user "if this single input moves
±delta, NPV moves between low and high." Sort descending by swing
and the chart reads as the headline contributor list. Pure
deterministic — no RNG, no IO; the same baseline + sensitivity
config produce identical output run-to-run.

The axis catalogue intentionally mirrors what the Monte Carlo wrapper
samples (weather, rate-escalation, degradation, hold-years), plus a
few capital-cost levers (system_cost, discount_rate) that don't need
a stochastic distribution to surface as sensitivities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from backend.engine.steps.dc_production import DcProductionResult
from backend.engine.steps.degradation import (
    DEFAULT_ANNUAL_LOSS,
    DEFAULT_FIRST_YEAR_LOSS,
    degradation_factors,
)
from backend.engine.steps.finance import run_finance
from backend.engine.steps.monte_carlo import _scaled_dc

if TYPE_CHECKING:
    from backend.engine.pipeline import ForecastState


class TornadoSensitivity(BaseModel):
    """How far each axis moves in each direction.

    Defaults are tuned to a realistic year-of-results spread:

    * weather: ±10 % captures NSRDB-vs-actual-year variability without
      exiting the schema's wind / temperature physical ranges.
    * rate_escalation: ±2 percentage points (utility tariff cases of
      record routinely move escalation forecasts by this much).
    * annual_loss: ±0.3 percentage points (NREL field-study spread).
    * hold_years: ±5 years (the headline "do you hold the home?" axis).
    * system_cost: ±10 % (installer-quote dispersion in the same ZIP).
    * discount_rate: ±2 percentage points (the difference between a
      mortgage discount and a stock-market opportunity-cost view).
    """

    weather_scale_delta: float = Field(0.10, ge=0.0, le=0.5)
    rate_escalation_delta: float = Field(0.02, ge=0.0, le=0.20)
    annual_loss_delta: float = Field(0.003, ge=0.0, le=0.05)
    hold_years_delta: int = Field(5, ge=0)
    system_cost_delta_pct: float = Field(0.10, ge=0.0, le=0.5)
    discount_rate_delta: float = Field(0.02, ge=0.0, le=0.20)


class TornadoAxis(BaseModel):
    """One row in the tornado chart.

    ``low_npv`` / ``high_npv`` are the NPVs at the negative / positive
    perturbation respectively, *not* min / max — direction matters
    when the axis is monotonic in NPV (more weather always helps,
    higher discount rate always hurts) and the chart renders the
    arrow accordingly.

    ``swing`` is ``abs(high_npv - low_npv)``; rows are emitted in
    descending swing order so the first entry is the headline lever.
    """

    name: str
    low_label: str
    high_label: str
    low_npv: float
    high_npv: float

    @property
    def swing(self) -> float:
        return abs(self.high_npv - self.low_npv)


class TornadoResult(BaseModel):
    """Sensitivity table + the baseline anchor.

    Consumers chart each row against ``baseline_npv`` so the bars
    extend outward from the baseline; the order of rows is the
    headline ranking.
    """

    sensitivity: TornadoSensitivity
    baseline_npv: float
    rows: list[TornadoAxis]


def run_tornado(
    state: ForecastState,
    *,
    sensitivity: TornadoSensitivity | None = None,
) -> TornadoResult:
    """Compute the tornado table for the forecast carried by ``state``.

    Preconditions match :func:`run_monte_carlo`: ``state`` already
    carries a baseline ``engine.dc_production`` and
    ``engine.consumption`` (run ``run_forecast`` first), and
    ``inputs.financial.system_cost`` + ``inputs.tariff.schedule`` are
    set.

    Runs ``2 * len(axes)`` finance evaluations — cheap because the
    expensive ModelChain pass isn't repeated. Each evaluation is a
    self-contained ``run_finance`` call against a baseline copy with
    one field swapped, so a buggy axis can't pollute the others.
    """
    inputs = state.inputs
    if inputs.financial.system_cost is None:
        raise ValueError("system_cost is required for tornado sensitivity")
    if inputs.tariff.schedule is None:
        raise ValueError("tariff.schedule is required for tornado sensitivity")
    dc = state.artifacts.get("engine.dc_production")
    if not isinstance(dc, DcProductionResult):
        raise ValueError("tornado requires engine.dc_production in state.artifacts")
    consumption = state.artifacts.get("engine.consumption")
    if not isinstance(consumption, list):
        raise ValueError("tornado requires engine.consumption in state.artifacts")

    sensitivity = sensitivity or TornadoSensitivity()
    baseline_npv = _evaluate_npv(
        _AxisInputs(
            financial=inputs.financial,
            consumption=consumption,
            dc=dc,
            schedule=inputs.tariff.schedule,
            export_credit=inputs.tariff.export_credit,
            annual_loss=DEFAULT_ANNUAL_LOSS,
            hold_years=inputs.financial.hold_years,
        )
    )

    rows: list[TornadoAxis] = []
    for axis in _AXES:
        if not axis.applicable(sensitivity):
            continue
        low_inputs = axis.perturb(_baseline_axis_inputs(state), sensitivity, sign=-1)
        high_inputs = axis.perturb(_baseline_axis_inputs(state), sensitivity, sign=+1)
        rows.append(
            TornadoAxis(
                name=axis.name,
                low_label=axis.low_label(sensitivity),
                high_label=axis.high_label(sensitivity),
                low_npv=_evaluate_npv(low_inputs),
                high_npv=_evaluate_npv(high_inputs),
            )
        )

    rows.sort(key=lambda row: row.swing, reverse=True)
    return TornadoResult(
        sensitivity=sensitivity,
        baseline_npv=baseline_npv,
        rows=rows,
    )


@dataclass
class _AxisInputs:
    """Mutable bundle of finance-step arguments threaded through one axis.

    Held as a dataclass rather than re-using ``ForecastInputs`` /
    ``ForecastState`` because the Pydantic models are immutable by
    convention and we want a cheap per-axis copy (every axis's
    ``perturb`` produces a fresh ``_AxisInputs`` and the original is
    discarded). ``annual_loss`` shadows the degradation-curve
    parameter so the curve can be rebuilt per axis without rebuilding
    the whole forecast.
    """

    financial: object  # FinancialInputs but typed-loose to avoid import cycle here
    consumption: list[float]
    dc: DcProductionResult
    schedule: object  # TariffSchedule
    export_credit: object | None
    annual_loss: float
    hold_years: int


def _baseline_axis_inputs(state: ForecastState) -> _AxisInputs:
    return _AxisInputs(
        financial=state.inputs.financial,
        consumption=state.artifacts["engine.consumption"],
        dc=state.artifacts["engine.dc_production"],
        schedule=state.inputs.tariff.schedule,
        export_credit=state.inputs.tariff.export_credit,
        annual_loss=DEFAULT_ANNUAL_LOSS,
        hold_years=state.inputs.financial.hold_years,
    )


def _evaluate_npv(axis: _AxisInputs) -> float:
    curve = degradation_factors(
        years=axis.hold_years,
        first_year_loss=DEFAULT_FIRST_YEAR_LOSS,
        annual_loss=axis.annual_loss,
    )
    # Cast back into the typed call: run_finance expects the
    # FinancialInputs Pydantic model. The typed-loose `object` carrier
    # in _AxisInputs is just plumbing; the actual runtime value is a
    # FinancialInputs with the per-axis override already applied.
    result = run_finance(
        financial=axis.financial,  # type: ignore[arg-type]
        consumption=axis.consumption,
        dc=axis.dc,
        degradation=curve,
        schedule=axis.schedule,  # type: ignore[arg-type]
        export_credit=axis.export_credit,  # type: ignore[arg-type]
    )
    return result.npv


# --- Axes ------------------------------------------------------------


@dataclass(frozen=True)
class _Axis:
    """Static description of one tornado lever.

    Each axis owns: which sensitivity field controls its delta, how
    to apply that delta to the bundle, and labels for the chart.
    Axes self-skip via ``applicable`` when their delta is zero so a
    user-configured "weather only" tornado is one config away.
    """

    name: str
    low_label_template: str
    high_label_template: str
    applicable_attr: str

    def applicable(self, s: TornadoSensitivity) -> bool:
        value = getattr(s, self.applicable_attr)
        return bool(value > 0)

    def low_label(self, s: TornadoSensitivity) -> str:
        return self.low_label_template.format(delta=getattr(s, self.applicable_attr))

    def high_label(self, s: TornadoSensitivity) -> str:
        return self.high_label_template.format(delta=getattr(s, self.applicable_attr))

    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        raise NotImplementedError


@dataclass(frozen=True)
class _WeatherAxis(_Axis):
    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        scale = 1.0 + sign * s.weather_scale_delta
        axis.dc = _scaled_dc(axis.dc, scale)
        return axis


@dataclass(frozen=True)
class _RateEscalationAxis(_Axis):
    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        from backend.engine.inputs import FinancialInputs

        baseline: FinancialInputs = axis.financial  # type: ignore[assignment]
        new_rate = baseline.rate_escalation + sign * s.rate_escalation_delta
        axis.financial = baseline.model_copy(update={"rate_escalation": new_rate})
        return axis


@dataclass(frozen=True)
class _AnnualLossAxis(_Axis):
    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        # Higher degradation = lower NPV → invert sign so the "high"
        # label still reads as more-degradation
        axis.annual_loss = max(0.0, axis.annual_loss + sign * s.annual_loss_delta)
        return axis


@dataclass(frozen=True)
class _HoldYearsAxis(_Axis):
    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        from backend.engine.inputs import FinancialInputs

        baseline: FinancialInputs = axis.financial  # type: ignore[assignment]
        new_hold = max(1, baseline.hold_years + sign * s.hold_years_delta)
        axis.financial = baseline.model_copy(update={"hold_years": new_hold})
        axis.hold_years = new_hold
        return axis


@dataclass(frozen=True)
class _SystemCostAxis(_Axis):
    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        from backend.engine.inputs import FinancialInputs

        baseline: FinancialInputs = axis.financial  # type: ignore[assignment]
        assert baseline.system_cost is not None
        new_cost = baseline.system_cost * (1.0 + sign * s.system_cost_delta_pct)
        axis.financial = baseline.model_copy(update={"system_cost": new_cost})
        return axis


@dataclass(frozen=True)
class _DiscountRateAxis(_Axis):
    def perturb(self, axis: _AxisInputs, s: TornadoSensitivity, *, sign: int) -> _AxisInputs:
        from backend.engine.inputs import FinancialInputs

        baseline: FinancialInputs = axis.financial  # type: ignore[assignment]
        new_rate = max(0.0, baseline.discount_rate + sign * s.discount_rate_delta)
        axis.financial = baseline.model_copy(update={"discount_rate": new_rate})
        return axis


_AXES: tuple[_Axis, ...] = (
    _WeatherAxis(
        name="weather",
        low_label_template="-{delta:.0%} sun",
        high_label_template="+{delta:.0%} sun",
        applicable_attr="weather_scale_delta",
    ),
    _RateEscalationAxis(
        name="rate_escalation",
        low_label_template="-{delta:.1%} escalation",
        high_label_template="+{delta:.1%} escalation",
        applicable_attr="rate_escalation_delta",
    ),
    _AnnualLossAxis(
        name="annual_loss",
        low_label_template="-{delta:.2%}/yr loss",
        high_label_template="+{delta:.2%}/yr loss",
        applicable_attr="annual_loss_delta",
    ),
    _HoldYearsAxis(
        name="hold_years",
        low_label_template="-{delta} yrs hold",
        high_label_template="+{delta} yrs hold",
        applicable_attr="hold_years_delta",
    ),
    _SystemCostAxis(
        name="system_cost",
        low_label_template="-{delta:.0%} system cost",
        high_label_template="+{delta:.0%} system cost",
        applicable_attr="system_cost_delta_pct",
    ),
    _DiscountRateAxis(
        name="discount_rate",
        low_label_template="-{delta:.1%} discount",
        high_label_template="+{delta:.1%} discount",
        applicable_attr="discount_rate_delta",
    ),
)


__all__ = [
    "TornadoAxis",
    "TornadoResult",
    "TornadoSensitivity",
    "run_tornado",
]

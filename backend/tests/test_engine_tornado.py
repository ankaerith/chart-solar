"""Tornado sensitivity wrapper (chart-solar-9ye).

Covers:

* axes are emitted in descending-swing order (the headline ranking
  the chart depends on)
* the baseline NPV anchor matches a direct ``run_finance`` call
* axes whose sensitivity delta is zero self-skip
* per-axis perturbation moves NPV in the expected direction (sun
  helps, escalation helps, degradation hurts, etc.)
* zero-delta sensitivity collapses to an empty row list (fast-path
  for callers that want to disable the tornado without removing it)
"""

from __future__ import annotations

import pytest

from backend.engine.inputs import (
    ConsumptionInputs,
    FinancialInputs,
    ForecastInputs,
    SegFlatConfig,
    SystemInputs,
    TariffInputs,
)
from backend.engine.pipeline import ForecastState, run_forecast
from backend.engine.steps.tornado import TornadoSensitivity, run_tornado
from backend.providers.fake import synthetic_tmy
from backend.providers.tariff import TariffSchedule


def _flat_tariff() -> TariffSchedule:
    return TariffSchedule(
        name="flat",
        utility="u",
        country="US",
        currency="USD",
        structure="flat",
        fixed_monthly_charge=10.0,
        flat_rate_per_kwh=0.20,
    )


def _baseline_state() -> ForecastState:
    """Run the pipeline once so the tornado wrapper has DC production +
    consumption to replay against. Mirrors what the forecast worker
    builds before invoking the wrapper in production."""
    inputs = ForecastInputs(
        system=SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(
            hold_years=20,
            system_cost=24_000.0,
            annual_opex=100.0,
            rate_escalation=0.025,
            discount_rate=0.06,
        ),
        tariff=TariffInputs(
            country="US",
            schedule=_flat_tariff(),
            export_credit=SegFlatConfig(flat_rate_per_kwh=0.05),
        ),
        consumption=ConsumptionInputs(annual_kwh=12_000.0),
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    result = run_forecast(inputs, tmy=tmy)
    return ForecastState(inputs=inputs, artifacts=dict(result.artifacts))


def test_run_tornado_returns_baseline_npv_matching_engine_finance() -> None:
    state = _baseline_state()
    finance_result = state.artifacts["engine.finance"]
    tornado = run_tornado(state)
    assert tornado.baseline_npv == pytest.approx(finance_result.npv, rel=1e-9)


def test_run_tornado_emits_default_six_axes_sorted_by_swing_descending() -> None:
    state = _baseline_state()
    tornado = run_tornado(state)
    assert len(tornado.rows) == 6
    swings = [row.swing for row in tornado.rows]
    assert swings == sorted(swings, reverse=True)


def test_run_tornado_sun_axis_moves_npv_in_expected_direction() -> None:
    """More sun = more production = higher NPV. The ``high`` label is
    tied to the +delta direction."""
    state = _baseline_state()
    tornado = run_tornado(state)
    weather = next(row for row in tornado.rows if row.name == "weather")
    assert weather.high_npv > weather.low_npv


def test_run_tornado_degradation_axis_moves_npv_inversely() -> None:
    """Higher degradation = less production over hold = lower NPV."""
    state = _baseline_state()
    tornado = run_tornado(state)
    annual_loss = next(row for row in tornado.rows if row.name == "annual_loss")
    assert annual_loss.high_npv < annual_loss.low_npv


def test_run_tornado_system_cost_axis_moves_npv_inversely() -> None:
    """A more expensive system depresses NPV (year-zero outflow grows)."""
    state = _baseline_state()
    tornado = run_tornado(state)
    cost = next(row for row in tornado.rows if row.name == "system_cost")
    assert cost.high_npv < cost.low_npv


def test_run_tornado_discount_rate_axis_moves_npv_inversely() -> None:
    """A higher discount rate compresses future cashflows; NPV falls."""
    state = _baseline_state()
    tornado = run_tornado(state)
    discount = next(row for row in tornado.rows if row.name == "discount_rate")
    assert discount.high_npv < discount.low_npv


def test_run_tornado_skips_axes_whose_delta_is_zero() -> None:
    """A user who wants only the weather axis sets the rest to zero
    delta; those axes drop out of the output."""
    sensitivity = TornadoSensitivity(
        weather_scale_delta=0.10,
        rate_escalation_delta=0.0,
        annual_loss_delta=0.0,
        hold_years_delta=0,
        system_cost_delta_pct=0.0,
        discount_rate_delta=0.0,
    )
    tornado = run_tornado(_baseline_state(), sensitivity=sensitivity)
    assert [row.name for row in tornado.rows] == ["weather"]


def test_run_tornado_zero_sensitivity_emits_no_rows() -> None:
    """A zero-everywhere sensitivity is a fast-path: the tornado is
    effectively disabled but the baseline anchor still comes through."""
    sensitivity = TornadoSensitivity(
        weather_scale_delta=0.0,
        rate_escalation_delta=0.0,
        annual_loss_delta=0.0,
        hold_years_delta=0,
        system_cost_delta_pct=0.0,
        discount_rate_delta=0.0,
    )
    tornado = run_tornado(_baseline_state(), sensitivity=sensitivity)
    assert tornado.rows == []
    assert tornado.baseline_npv == pytest.approx(
        _baseline_state().artifacts["engine.finance"].npv, rel=1e-9
    )


def test_run_tornado_axis_perturbations_dont_leak_into_each_other() -> None:
    """Order independence: shuffling the axis evaluation order can't
    change any individual row's low/high values. Each perturb call
    works against a fresh baseline copy.

    Re-running the wrapper twice must produce identical numbers (the
    wrapper is deterministic — no RNG)."""
    state = _baseline_state()
    a = run_tornado(state)
    b = run_tornado(state)
    rows_a = {row.name: (row.low_npv, row.high_npv) for row in a.rows}
    rows_b = {row.name: (row.low_npv, row.high_npv) for row in b.rows}
    assert rows_a == rows_b


def test_run_tornado_requires_system_cost_in_inputs() -> None:
    """A baseline without ``system_cost`` can't produce NPV — the
    wrapper raises rather than silently zero-rowing."""
    inputs = ForecastInputs(
        system=SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(hold_years=20),  # no system_cost
        tariff=TariffInputs(country="US", schedule=_flat_tariff()),
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    result = run_forecast(inputs, tmy=tmy)
    state = ForecastState(inputs=inputs, artifacts=dict(result.artifacts))
    with pytest.raises(ValueError, match="system_cost"):
        run_tornado(state)

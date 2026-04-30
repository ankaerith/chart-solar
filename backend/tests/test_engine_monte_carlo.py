"""Monte Carlo wrapper tests.

Covers determinism (same seed → same paths), distribution shape (P10 ≤
P50 ≤ P90), the rectangular cumulative-fan invariant when hold_years
varies, and a 10-path mini run on the example fixture system as the
acceptance-criteria smoke. The 500-path budget claim from the bead's
acceptance criteria is exercised separately and flagged ``slow`` so a
default ``pytest`` invocation isn't penalised by the perf check.
"""

from __future__ import annotations

import time

import pytest

from backend.engine.inputs import (
    ConsumptionInputs,
    FinancialInputs,
    ForecastInputs,
    SegFlatConfig,
    SystemInputs,
    TariffInputs,
)
from backend.engine.pipeline import ForecastResult, ForecastState, run_forecast
from backend.engine.steps.monte_carlo import (
    MonteCarloResult,
    MonteCarloSampling,
    run_monte_carlo,
)
from backend.providers.fake import synthetic_tmy
from backend.providers.tariff import TariffSchedule


def _flat_tariff() -> TariffSchedule:
    return TariffSchedule(
        name="MC test flat",
        utility="utility-test",
        country="US",
        currency="USD",
        structure="flat",
        fixed_monthly_charge=10.0,
        flat_rate_per_kwh=0.18,
    )


def _seeded_inputs() -> ForecastInputs:
    """Concrete inputs that drive a meaningful finance roll-up.

    The default ``example_inputs`` fixture omits ``system_cost`` and
    consumption — finance + Monte Carlo both require those, so the MC
    suite ships its own inputs builder rather than mutating the shared
    fixture.
    """
    # Sized so annual production < annual consumption — every produced
    # kWh offsets a full retail kWh, which makes the finance numbers
    # behave reliably enough for percentile-ordering assertions.
    return ForecastInputs(
        system=SystemInputs(lat=37.4, lon=-122.1, dc_kw=6.0, tilt_deg=20, azimuth_deg=180),
        financial=FinancialInputs(
            discount_rate=0.04,
            hold_years=20,
            system_cost=15_000.0,
            annual_opex=120.0,
            rate_escalation=0.03,
        ),
        tariff=TariffInputs(
            country="US",
            schedule=_flat_tariff(),
            export_credit=SegFlatConfig(flat_rate_per_kwh=0.05),
        ),
        consumption=ConsumptionInputs(annual_kwh=20_000.0),
    )


def _baseline_state(inputs: ForecastInputs) -> ForecastState:
    """Run the full pipeline once and return the resulting state.

    Monte Carlo consumes ``state.artifacts['engine.dc_production']`` +
    ``engine.consumption`` — anything else is recomputed per path.
    """
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    result: ForecastResult = run_forecast(inputs, tmy=tmy)
    return ForecastState(inputs=result.inputs, artifacts=dict(result.artifacts))


def test_deterministic_with_seed() -> None:
    """Same seed → byte-identical NPV path arrays.

    Finance worker persists the seed alongside the artifact so users
    can re-run; this test pins the contract.
    """
    state = _baseline_state(_seeded_inputs())
    a = run_monte_carlo(state, n=10, seed=42)
    b = run_monte_carlo(state, n=10, seed=42)
    assert a.npv_paths == b.npv_paths
    assert a.cumulative_paths == b.cumulative_paths
    assert a.npv == b.npv


def test_different_seeds_produce_different_paths() -> None:
    state = _baseline_state(_seeded_inputs())
    a = run_monte_carlo(state, n=10, seed=1)
    b = run_monte_carlo(state, n=10, seed=2)
    assert a.npv_paths != b.npv_paths


def test_percentiles_are_ordered() -> None:
    state = _baseline_state(_seeded_inputs())
    result = run_monte_carlo(state, n=50, seed=7)
    assert result.npv.p10 <= result.npv.p50 <= result.npv.p90
    assert result.payback_years is not None
    assert result.payback_years.p10 <= result.payback_years.p50 <= result.payback_years.p90


def test_cumulative_fan_per_year_is_ordered() -> None:
    """Each year's P10 ≤ P50 ≤ P90 across the fan-chart series."""
    state = _baseline_state(_seeded_inputs())
    result = run_monte_carlo(state, n=50, seed=11)
    for year_pct in result.cumulative_net_wealth:
        assert year_pct.p10 <= year_pct.p50 <= year_pct.p90


def test_year_zero_cumulative_is_negative_capex() -> None:
    """The fan starts at the homeowner's outlay (cash-buy: -system_cost).

    Year 0 has no sampled axis affecting it, so all paths share the
    same year-0 cashflow and the percentile band collapses to a point.
    """
    inputs = _seeded_inputs()
    state = _baseline_state(inputs)
    result = run_monte_carlo(state, n=20, seed=3)
    assert result.cumulative_net_wealth[0].p10 == result.cumulative_net_wealth[0].p90
    assert inputs.financial.system_cost is not None
    assert result.cumulative_net_wealth[0].p50 == pytest.approx(-inputs.financial.system_cost)


def test_cumulative_horizon_matches_hold_years_with_no_jitter() -> None:
    inputs = _seeded_inputs()
    state = _baseline_state(inputs)
    result = run_monte_carlo(state, n=10, seed=0)
    # hold_years inflows + year 0 outflow → hold_years + 1 entries.
    assert len(result.cumulative_net_wealth) == inputs.financial.hold_years + 1


def test_hold_jitter_pads_short_paths_to_max_horizon() -> None:
    inputs = _seeded_inputs()
    state = _baseline_state(inputs)
    sampling = MonteCarloSampling(hold_years_jitter=3)
    result = run_monte_carlo(state, n=30, seed=99, sampling=sampling)
    # Every per-path cumulative array can differ in length; the fan
    # series uses the longest path's horizon.
    horizons = {len(p) for p in result.cumulative_paths}
    assert len(horizons) > 1
    assert len(result.cumulative_net_wealth) == max(horizons)


def test_zero_variance_sampling_collapses_to_baseline_point() -> None:
    """σ=0 across every axis → every path identical → P10=P50=P90.

    Confirms the wrapper isn't accidentally adding noise of its own
    beyond the configured sampling distribution.
    """
    state = _baseline_state(_seeded_inputs())
    sampling = MonteCarloSampling(
        rate_escalation_std=0.0,
        annual_loss_std=0.0,
        weather_scale_std=0.0,
        hold_years_jitter=0,
    )
    result = run_monte_carlo(state, n=5, seed=0, sampling=sampling)
    assert result.npv.p10 == result.npv.p50 == result.npv.p90
    assert all(p == result.npv_paths[0] for p in result.npv_paths)


def test_mini_run_smoke_on_fixture_system() -> None:
    """Acceptance criterion (6): 10-path Monte Carlo on the fixture system."""
    state = _baseline_state(_seeded_inputs())
    result = run_monte_carlo(state, n=10, seed=2026)
    assert isinstance(result, MonteCarloResult)
    assert result.n == 10
    assert len(result.npv_paths) == 10
    assert result.failed_paths == 0


def test_rejects_state_without_dc_production() -> None:
    inputs = _seeded_inputs()
    state = ForecastState(inputs=inputs, artifacts={"engine.consumption": [0.0] * 8760})
    with pytest.raises(ValueError, match="engine.dc_production"):
        run_monte_carlo(state, n=2, seed=0)


def test_rejects_state_without_consumption() -> None:
    inputs = _seeded_inputs()
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    full = run_forecast(inputs, tmy=tmy)
    artifacts = dict(full.artifacts)
    del artifacts["engine.consumption"]
    state = ForecastState(inputs=full.inputs, artifacts=artifacts)
    with pytest.raises(ValueError, match="engine.consumption"):
        run_monte_carlo(state, n=2, seed=0)


def test_rejects_inputs_missing_system_cost() -> None:
    inputs = _seeded_inputs()
    inputs = inputs.model_copy(
        update={"financial": inputs.financial.model_copy(update={"system_cost": None})}
    )
    state = _baseline_state(_seeded_inputs())
    state = ForecastState(inputs=inputs, artifacts=state.artifacts)
    with pytest.raises(ValueError, match="system_cost"):
        run_monte_carlo(state, n=2, seed=0)


def test_rejects_n_below_one() -> None:
    state = _baseline_state(_seeded_inputs())
    with pytest.raises(ValueError, match="n must be >= 1"):
        run_monte_carlo(state, n=0, seed=0)


@pytest.mark.slow
def test_500_path_run_within_budget() -> None:
    """Acceptance criterion (4): 500 paths in < 60s on a small machine.

    Marked ``slow`` so default ``pytest`` invocations skip it; CI can
    opt in via ``-m slow``. The 60s cap is generous — local runs come
    in well under, but Fly's smallest machine has half the CPU.
    """
    state = _baseline_state(_seeded_inputs())
    start = time.perf_counter()
    result = run_monte_carlo(state, n=500, seed=0)
    elapsed = time.perf_counter() - start
    assert len(result.npv_paths) + result.failed_paths == 500
    assert elapsed < 60.0, f"500-path Monte Carlo took {elapsed:.1f}s (budget 60s)"

"""Year-over-year degradation curve.

Pure-math tests for the degradation step — no pvlib, no providers.
The function is small but its behaviour gates a lot of downstream
math (NPV / IRR sensitivity, tornado plot), so we pin every contract
explicitly.
"""

from __future__ import annotations

import math

import pytest

from backend.engine.steps.degradation import (
    DEFAULT_ANNUAL_LOSS,
    DEFAULT_FIRST_YEAR_LOSS,
    DegradationCurve,
    apply_degradation,
    degradation_factors,
    warranty_endpoint,
)


def test_default_curve_year1_factor_is_98pct() -> None:
    curve = degradation_factors(years=25)
    assert curve.factors[0] == pytest.approx(1.0 - DEFAULT_FIRST_YEAR_LOSS)


def test_default_linear_curve_year25_above_industry_warranty_floor() -> None:
    """Tier-1 module warranties typically promise ≥80 % at year 25;
    the default curve must clear that comfortably (≥84 %)."""
    curve = degradation_factors(years=25)
    assert warranty_endpoint(curve) >= 0.84


def test_linear_curve_steps_down_by_annual_loss_each_year() -> None:
    curve = degradation_factors(
        years=10,
        first_year_loss=0.02,
        annual_loss=0.005,
        model="linear",
    )
    for t, factor in enumerate(curve.factors):
        expected = 0.98 - 0.005 * t
        assert factor == pytest.approx(expected, abs=1e-12)


def test_geometric_curve_compounds_annual_loss() -> None:
    curve = degradation_factors(
        years=10,
        first_year_loss=0.02,
        annual_loss=0.005,
        model="geometric",
    )
    for t, factor in enumerate(curve.factors):
        expected = 0.98 * (1.0 - 0.005) ** t
        assert factor == pytest.approx(expected, abs=1e-12)


def test_geometric_above_linear_after_year1_at_same_inputs() -> None:
    """Geometric decay loses less than linear over time at the same
    annual_loss because each year's loss is a fraction of a *smaller*
    base — diverges by ~1-2 % over a 25-year run."""
    linear = degradation_factors(years=25, model="linear")
    geometric = degradation_factors(years=25, model="geometric")
    # Year 1 matches by construction
    assert linear.factors[0] == pytest.approx(geometric.factors[0])
    # All subsequent years: geometric is higher
    for lin, geo in zip(linear.factors[1:], geometric.factors[1:], strict=True):
        assert geo > lin


def test_zero_first_year_loss_starts_at_one() -> None:
    curve = degradation_factors(years=5, first_year_loss=0.0, annual_loss=0.005)
    assert curve.factors[0] == pytest.approx(1.0)


def test_zero_annual_loss_yields_flat_curve_after_year1() -> None:
    curve = degradation_factors(years=5, first_year_loss=0.02, annual_loss=0.0)
    for f in curve.factors:
        assert f == pytest.approx(0.98)


def test_clamps_at_zero_for_pathological_inputs() -> None:
    """A wildly aggressive annual_loss × years combo would push
    factors negative under linear; we clamp at zero so downstream
    integration over kWh × factor never goes negative."""
    curve = degradation_factors(
        years=50,
        first_year_loss=0.0,
        annual_loss=0.05,
        model="linear",
    )
    assert min(curve.factors) >= 0.0
    assert curve.factors[-1] == pytest.approx(0.0)


def test_one_year_horizon_returns_single_factor() -> None:
    curve = degradation_factors(years=1)
    assert len(curve.factors) == 1
    assert curve.factors[0] == pytest.approx(1.0 - DEFAULT_FIRST_YEAR_LOSS)


def test_apply_degradation_scales_year1_kwh_per_year() -> None:
    curve = degradation_factors(years=5)
    yearly = apply_degradation(year_one_kwh=10_000.0, curve=curve)
    for kwh, factor in zip(yearly, curve.factors, strict=True):
        assert kwh == pytest.approx(10_000.0 * factor)


def test_apply_degradation_zero_year1_returns_zeros() -> None:
    curve = degradation_factors(years=5)
    yearly = apply_degradation(year_one_kwh=0.0, curve=curve)
    assert all(kwh == 0.0 for kwh in yearly)


def test_apply_degradation_rejects_negative_year1() -> None:
    curve = degradation_factors(years=5)
    with pytest.raises(ValueError, match="year_one_kwh must be >= 0"):
        apply_degradation(year_one_kwh=-1.0, curve=curve)


def test_curve_round_trips_through_json() -> None:
    """Engine state crosses the queue boundary as JSON; the curve must
    survive `model_dump(mode="json") -> model_validate`."""
    curve = degradation_factors(years=25)
    payload = curve.model_dump(mode="json")
    revived = DegradationCurve.model_validate(payload)
    assert revived.years == curve.years
    assert revived.model == curve.model
    for a, b in zip(revived.factors, curve.factors, strict=True):
        assert math.isclose(a, b, abs_tol=1e-12)


def test_default_annual_loss_matches_nrel_field_study_median() -> None:
    """Pin the default in case future changes drift it — the docstring
    on `DEFAULT_ANNUAL_LOSS` claims the NREL field-study figure."""
    assert DEFAULT_ANNUAL_LOSS == pytest.approx(0.0055)


def test_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="years must be >= 1"):
        degradation_factors(years=0)
    with pytest.raises(ValueError, match="first_year_loss must be in"):
        degradation_factors(years=5, first_year_loss=1.0)
    with pytest.raises(ValueError, match="annual_loss must be in"):
        degradation_factors(years=5, annual_loss=1.0)
    with pytest.raises(ValueError, match="unknown degradation model"):
        degradation_factors(years=5, model="exponential")  # type: ignore[arg-type]

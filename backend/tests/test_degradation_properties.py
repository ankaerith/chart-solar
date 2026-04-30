"""Property-based tests for engine.degradation.

Invariants that must hold across the input space:

- The curve is monotonically non-increasing year over year — solar
  modules don't recover capacity.
- Year 1 factor equals ``1 - first_year_loss`` exactly.
- For ``model='linear'``: factor[t] == (1 - first) - annual_loss × t
  (clamped at 0).
- For ``model='geometric'``: factor[t] == (1 - first) × (1 - annual)^t
  (clamped at 0).
- ``warranty_endpoint`` returns the smallest factor in the curve.
- ``apply_degradation`` scales linearly: doubling year-1 kWh doubles
  every per-year output.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.engine.steps.degradation import (
    apply_degradation,
    degradation_factors,
    warranty_endpoint,
)

settings.register_profile("ci", max_examples=200, deadline=None)
settings.register_profile(
    "nightly",
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("ci")


_years = st.integers(min_value=1, max_value=40)
_first_year_loss = st.floats(min_value=0.0, max_value=0.20, allow_nan=False, allow_infinity=False)
_annual_loss = st.floats(min_value=0.0, max_value=0.05, allow_nan=False, allow_infinity=False)
_model = st.sampled_from(["linear", "geometric"])


@given(years=_years, first=_first_year_loss, annual=_annual_loss, model=_model)
def test_curve_is_monotonic_non_increasing(
    years: int, first: float, annual: float, model: str
) -> None:
    """Solar modules don't recover capacity — every step must be ≤ the
    previous step. Equality is allowed (annual_loss == 0) and at the
    zero-clamp floor."""
    curve = degradation_factors(
        years=years,
        first_year_loss=first,
        annual_loss=annual,
        model=model,  # type: ignore[arg-type]
    )
    for prev, nxt in zip(curve.factors, curve.factors[1:], strict=False):
        assert nxt <= prev + 1e-12


@given(years=_years, first=_first_year_loss, annual=_annual_loss, model=_model)
def test_year_one_factor_matches_first_year_loss(
    years: int, first: float, annual: float, model: str
) -> None:
    """Year 1 sits at exactly ``1 - first_year_loss`` — the annual
    decline only kicks in past year 1."""
    curve = degradation_factors(
        years=years,
        first_year_loss=first,
        annual_loss=annual,
        model=model,  # type: ignore[arg-type]
    )
    assert curve.factors[0] == pytest.approx(1.0 - first, abs=1e-12)


@given(years=_years, first=_first_year_loss, annual=_annual_loss)
def test_linear_curve_matches_closed_form(years: int, first: float, annual: float) -> None:
    """Linear curve: factor[t] == (1-first) - annual × t, floored at 0."""
    curve = degradation_factors(
        years=years, first_year_loss=first, annual_loss=annual, model="linear"
    )
    year_one = 1.0 - first
    for t, factor in enumerate(curve.factors):
        expected = max(0.0, year_one - annual * t)
        assert math.isclose(factor, expected, rel_tol=1e-9, abs_tol=1e-12)


@given(years=_years, first=_first_year_loss, annual=_annual_loss)
def test_geometric_curve_matches_closed_form(years: int, first: float, annual: float) -> None:
    """Geometric curve: factor[t] == (1-first) × (1-annual)^t."""
    curve = degradation_factors(
        years=years, first_year_loss=first, annual_loss=annual, model="geometric"
    )
    year_one = 1.0 - first
    for t, factor in enumerate(curve.factors):
        expected = max(0.0, year_one * (1.0 - annual) ** t)
        assert math.isclose(factor, expected, rel_tol=1e-9, abs_tol=1e-12)


@given(years=_years, first=_first_year_loss, annual=_annual_loss, model=_model)
def test_warranty_endpoint_is_smallest_factor(
    years: int, first: float, annual: float, model: str
) -> None:
    """Because the curve is non-increasing, the last factor is the
    smallest. ``warranty_endpoint`` must return that value."""
    curve = degradation_factors(
        years=years,
        first_year_loss=first,
        annual_loss=annual,
        model=model,  # type: ignore[arg-type]
    )
    assert warranty_endpoint(curve) == min(curve.factors)


@given(
    years=_years,
    first=_first_year_loss,
    annual=_annual_loss,
    model=_model,
    base_kwh=st.floats(min_value=1_000.0, max_value=50_000.0),
    scale=st.floats(min_value=0.5, max_value=4.0),
)
def test_apply_degradation_scales_linearly(
    years: int,
    first: float,
    annual: float,
    model: str,
    base_kwh: float,
    scale: float,
) -> None:
    """``apply_degradation`` is just multiplication: scaling year-1
    kWh by k scales every per-year output by k."""
    curve = degradation_factors(
        years=years,
        first_year_loss=first,
        annual_loss=annual,
        model=model,  # type: ignore[arg-type]
    )
    base = apply_degradation(base_kwh, curve)
    scaled = apply_degradation(base_kwh * scale, curve)
    for b, s in zip(base, scaled, strict=True):
        assert math.isclose(s, b * scale, rel_tol=1e-9, abs_tol=1e-9)

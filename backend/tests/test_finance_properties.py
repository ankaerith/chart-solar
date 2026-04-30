"""Property-based tests for engine finance math (chart-solar-8lll).

Where the example tests in ``test_finance_amortization.py`` /
``test_finance_cashflow.py`` pin specific numeric outputs, these
tests assert *invariants* that must hold across the input space:

- Amortization: every schedule's payments sum to principal + total
  interest; payment amount is monotonic in APR (within the same
  principal/term).
- NPV: ``npv(0, cf) == sum(cf)`` (zero-rate identity); NPV is
  monotonic in the discount rate when the stream is dominated by
  out-of-year-0 inflows.
- IRR: when an IRR exists, ``npv(irr_value, cf) ≈ 0``; cashflow
  streams without a sign change raise rather than return a
  meaningless value.

CI runs at the default Hypothesis budget (~100 examples per
property). The nightly profile bumps to 1000 — register it with
``hypothesis.settings.register_profile`` and call it via
``HYPOTHESIS_PROFILE=nightly pytest`` from the nightly workflow.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from backend.engine.finance import (
    amortize,
    irr,
    npv,
)

# Profiles for CI + nightly. Default deadline is generous so the slow
# bisection in IRR doesn't flake on cold-cache CI shards.
settings.register_profile("ci", max_examples=200, deadline=None)
settings.register_profile(
    "nightly",
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("ci")


# Strategies ---------------------------------------------------------


_principal = st.floats(
    min_value=1_000.0, max_value=500_000.0, allow_nan=False, allow_infinity=False
)
_apr = st.floats(min_value=0.0, max_value=0.25, allow_nan=False, allow_infinity=False)
_term_months = st.integers(min_value=12, max_value=360)


@st.composite
def _solar_cashflow(draw: st.DrawFn) -> list[float]:
    """A solar-shaped cashflow stream: year-0 outflow, future inflows
    bounded above and below to keep IRR's bracket reasonable."""
    n_years = draw(st.integers(min_value=2, max_value=30))
    capex = -draw(st.floats(min_value=5_000.0, max_value=80_000.0))
    annual = draw(st.floats(min_value=200.0, max_value=15_000.0))
    return [capex] + [annual] * n_years


# Amortization properties -------------------------------------------


@given(principal=_principal, apr=_apr, term_months=_term_months)
def test_payments_sum_to_principal_plus_interest(
    principal: float, apr: float, term_months: int
) -> None:
    """Σ(payments) == principal + total_interest, within float tolerance.

    Holds because each row's ``payment = interest + principal_paid``
    and the schedule consumes the full principal.
    """
    schedule = amortize(principal, apr, term_months)
    total_paid = sum(row.payment for row in schedule.rows)
    assert math.isclose(
        total_paid,
        principal + schedule.total_interest,
        rel_tol=1e-9,
        abs_tol=1e-6,
    )


@given(principal=_principal, term_months=_term_months, low=_apr, high=_apr)
def test_payment_monotonic_in_apr(
    principal: float, term_months: int, low: float, high: float
) -> None:
    """Higher APR ⇒ higher monthly payment (same principal/term).

    The mortgage formula is monotonic in rate; this just guards
    against accidental sign-flips inside ``monthly_payment``. Rates
    must differ by more than the function's float-noise floor — at
    sub-microscopic deltas the FP error in the payment formula can
    invert the sign of the change.
    """
    assume(high - low > 1e-4)
    low_pmt = amortize(principal, low, term_months).rows[0].payment
    high_pmt = amortize(principal, high, term_months).rows[0].payment
    assert high_pmt >= low_pmt


@given(principal=_principal, term_months=_term_months)
def test_zero_apr_collapses_to_even_principal_split(principal: float, term_months: int) -> None:
    """At APR=0 every payment is principal-only; total interest is 0
    and per-month payment is principal / term_months."""
    schedule = amortize(principal, 0.0, term_months)
    expected_payment = principal / term_months
    assert schedule.total_interest == pytest.approx(0.0, abs=1e-6)
    for row in schedule.rows:
        assert row.interest == 0.0
        # Last row may carry a one-cent residue from float rounding.
        assert math.isclose(row.payment, expected_payment, rel_tol=1e-6, abs_tol=1e-2)


@given(principal=_principal, apr=_apr, term_months=_term_months)
def test_balance_decreases_monotonically(principal: float, apr: float, term_months: int) -> None:
    """Outstanding balance never increases month-over-month — even at
    APR=0 (where principal_paid is exactly even) the balance trends
    monotonically to zero."""
    schedule = amortize(principal, apr, term_months)
    previous = principal
    for row in schedule.rows:
        assert row.balance <= previous + 1e-6
        previous = row.balance
    assert schedule.rows[-1].balance == pytest.approx(0.0, abs=1e-6)


# NPV properties -----------------------------------------------------


@given(
    cashflows=st.lists(
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=30,
    )
)
def test_npv_zero_rate_equals_sum_of_cashflows(cashflows: list[float]) -> None:
    """NPV(0) is the undiscounted total — the discount factor (1+r)^t
    collapses to 1 at every horizon."""
    assert math.isclose(npv(0.0, cashflows), sum(cashflows), rel_tol=1e-9, abs_tol=1e-6)


@given(cashflows=_solar_cashflow(), low=st.floats(min_value=0.0, max_value=0.10))
def test_npv_monotonic_decreasing_in_rate_for_positive_streams(
    cashflows: list[float], low: float
) -> None:
    """For a year-0-outflow + uniform-positive-inflows stream (the
    canonical solar shape), NPV is monotonically *decreasing* in the
    discount rate: future dollars are worth less the more you discount.
    """
    high = low + 0.05
    npv_low = npv(low, cashflows)
    npv_high = npv(high, cashflows)
    assert npv_low >= npv_high - 1e-6


# IRR properties -----------------------------------------------------


@given(cashflows=_solar_cashflow())
def test_irr_zeroes_npv_when_one_exists(cashflows: list[float]) -> None:
    """The defining property of IRR: NPV at the IRR rate equals zero.

    Solar-shaped streams always have a unique positive IRR, so the
    bisection always converges. Tolerance is loose because float NPV
    accumulation introduces small residue.
    """
    rate = irr(cashflows)
    assert math.isclose(npv(rate, cashflows), 0.0, abs_tol=1e-3)


@given(
    n_years=st.integers(min_value=2, max_value=20),
    inflow=st.floats(min_value=100.0, max_value=10_000.0),
)
def test_irr_rejects_strictly_positive_streams(n_years: int, inflow: float) -> None:
    """A stream with no negative entry has no finite IRR — the
    function must raise rather than silently return a meaningless rate.
    """
    cashflows = [inflow] * n_years
    with pytest.raises(ValueError, match="positive and one negative"):
        irr(cashflows)


@given(
    n_years=st.integers(min_value=2, max_value=20),
    outflow=st.floats(min_value=100.0, max_value=10_000.0),
)
def test_irr_rejects_strictly_negative_streams(n_years: int, outflow: float) -> None:
    """Symmetrically, an all-negative stream has no IRR."""
    cashflows = [-outflow] * n_years
    with pytest.raises(ValueError, match="positive and one negative"):
        irr(cashflows)

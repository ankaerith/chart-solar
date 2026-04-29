"""Loan amortization (fixed + variable) + dealer-fee unmasking.

These are pure-math tests — no DB, no providers. They pin the
schedule shape against textbook formulas and known dealer-loan
scenarios so the engine's finance step has a stable foundation.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from backend.engine.finance import (
    AmortizationRow,
    AmortizationSchedule,
    amortize,
    amortize_variable,
    dealer_fee_effective_apr,
    monthly_payment,
)


def _expected_payment(p: float, apr: float, n: int) -> float:
    """Reference implementation — direct from the formula."""
    if apr == 0:
        return p / n
    r = apr / 12.0
    return p * r * (1 + r) ** n / ((1 + r) ** n - 1)


def test_monthly_payment_matches_textbook_formula() -> None:
    p, apr, n = 25_000.0, 0.0499, 25 * 12
    assert monthly_payment(p, apr, n) == pytest.approx(_expected_payment(p, apr, n))


def test_monthly_payment_zero_apr_is_even_split() -> None:
    p, n = 12_000.0, 24
    assert monthly_payment(p, 0.0, n) == pytest.approx(p / n)


def test_monthly_payment_zero_principal_is_zero() -> None:
    assert monthly_payment(0.0, 0.05, 60) == pytest.approx(0.0)


def test_monthly_payment_rejects_zero_term() -> None:
    with pytest.raises(ValueError, match="term_months must be positive"):
        monthly_payment(1000.0, 0.05, 0)


def test_amortize_full_schedule_closes_to_zero() -> None:
    schedule = amortize(principal=20_000.0, apr=0.0599, term_months=300)
    assert schedule.term_months == 300
    assert len(schedule.rows) == 300
    assert schedule.rows[-1].balance == pytest.approx(0.0, abs=0.005)
    # Every row's payment / interest / principal sums correctly.
    for row in schedule.rows:
        assert row.payment == pytest.approx(row.interest + row.principal_paid)


def test_amortize_total_paid_equals_principal_plus_interest() -> None:
    schedule = amortize(principal=15_000.0, apr=0.069, term_months=120)
    assert schedule.total_paid == pytest.approx(
        schedule.principal + schedule.total_interest, abs=0.01
    )


def test_amortize_zero_apr_payment_is_constant_principal_split() -> None:
    schedule = amortize(principal=12_000.0, apr=0.0, term_months=24)
    expected_payment = 500.0
    for row in schedule.rows:
        assert row.payment == pytest.approx(expected_payment)
        assert row.interest == pytest.approx(0.0)
        assert row.principal_paid == pytest.approx(expected_payment)


def test_amortize_first_payment_matches_monthly_payment_formula() -> None:
    p, apr, n = 30_000.0, 0.0499, 25 * 12
    schedule = amortize(principal=p, apr=apr, term_months=n)
    assert schedule.rows[0].payment == pytest.approx(_expected_payment(p, apr, n))


def test_amortize_last_row_squashes_floating_point_residue() -> None:
    """The final row absorbs any rounding residue so the schedule
    closes at exactly 0 — important for downstream NPV / IRR which
    integrate the cashflow."""
    schedule = amortize(principal=29_999.99, apr=0.075, term_months=180)
    assert schedule.rows[-1].balance == 0.0


def test_amortize_rejects_negative_principal() -> None:
    with pytest.raises(ValueError, match="principal must be >= 0"):
        amortize(principal=-1.0, apr=0.05, term_months=60)


def test_amortize_variable_constant_rate_matches_fixed() -> None:
    """A variable schedule with the same rate every month must match
    the fixed-rate amortization to within float tolerance."""
    p, apr, n = 25_000.0, 0.0599, 240
    fixed = amortize(principal=p, apr=apr, term_months=n)
    variable = amortize_variable(principal=p, monthly_rates=[apr / 12.0] * n)
    assert variable.term_months == n
    for f, v in zip(fixed.rows, variable.rows, strict=True):
        assert f.payment == pytest.approx(v.payment)
        assert f.balance == pytest.approx(v.balance)


def test_amortize_variable_rate_step_up_recomputes_payment() -> None:
    """Step the rate up halfway through; payment must rise on the step
    and the schedule must still close at zero."""
    rates = [0.05 / 12.0] * 30 + [0.10 / 12.0] * 30
    schedule = amortize_variable(principal=10_000.0, monthly_rates=rates)
    assert schedule.rows[-1].balance == pytest.approx(0.0, abs=0.01)
    payment_before_step = schedule.rows[29].payment
    payment_after_step = schedule.rows[30].payment
    assert payment_after_step > payment_before_step


def test_amortize_variable_rejects_empty_rates() -> None:
    with pytest.raises(ValueError, match="must be non-empty"):
        amortize_variable(principal=10_000.0, monthly_rates=[])


def test_dealer_fee_zero_returns_stated_apr() -> None:
    """No dealer fee = stated APR is the real APR."""
    eff = dealer_fee_effective_apr(
        cash_price=30_000.0,
        stated_apr=0.0499,
        dealer_fee_pct=0.0,
        term_months=300,
    )
    assert eff == pytest.approx(0.0499, abs=1e-4)


def test_dealer_fee_18_pct_at_499_apr_inflates_real_cost() -> None:
    """Industry-typical scenario: 4.99% stated, 18% dealer fee → ~6.7%
    real APR for a 25-year loan. Dealer fee is amortized across the
    long term, so the per-year markup is smaller than for a 5-year
    loan (where the same 18% dealer fee inflates the effective APR
    much more dramatically — the audit's "long-term dealer-loan"
    flag is mostly about catching this lower-but-still-real markup)."""
    eff = dealer_fee_effective_apr(
        cash_price=30_000.0,
        stated_apr=0.0499,
        dealer_fee_pct=0.18,
        term_months=300,
    )
    # Sanity bounds — clearly > stated rate, clearly less than 30%.
    assert eff > 0.0499
    assert eff > 0.06
    assert eff < 0.30


def test_dealer_fee_higher_fee_means_higher_effective_apr() -> None:
    """Monotonic in dealer fee (holding everything else fixed)."""
    base = dealer_fee_effective_apr(
        cash_price=30_000.0,
        stated_apr=0.0499,
        dealer_fee_pct=0.10,
        term_months=300,
    )
    high = dealer_fee_effective_apr(
        cash_price=30_000.0,
        stated_apr=0.0499,
        dealer_fee_pct=0.25,
        term_months=300,
    )
    assert high > base


def test_dealer_fee_effective_payment_present_value_matches_cash_price() -> None:
    """The whole point of the function: the present value of the actual
    monthly payments, discounted at the *effective* rate, must equal
    the cash price (the real benefit received)."""
    cash, stated, fee, n = 28_000.0, 0.0599, 0.20, 240
    eff = dealer_fee_effective_apr(
        cash_price=cash,
        stated_apr=stated,
        dealer_fee_pct=fee,
        term_months=n,
    )
    financed = cash * (1.0 + fee)
    payment = monthly_payment(financed, stated, n)
    eff_monthly = eff / 12.0
    pv = payment * (1.0 - (1.0 + eff_monthly) ** -n) / eff_monthly
    assert pv == pytest.approx(cash, rel=1e-3)


def test_dealer_fee_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        dealer_fee_effective_apr(
            cash_price=-1.0, stated_apr=0.05, dealer_fee_pct=0.10, term_months=60
        )
    with pytest.raises(ValueError):
        dealer_fee_effective_apr(
            cash_price=10_000.0, stated_apr=0.05, dealer_fee_pct=1.0, term_months=60
        )
    with pytest.raises(ValueError):
        dealer_fee_effective_apr(
            cash_price=10_000.0, stated_apr=0.05, dealer_fee_pct=0.10, term_months=0
        )


def test_amortization_row_rejects_negative_payment() -> None:
    with pytest.raises(ValidationError):
        AmortizationRow(month=1, payment=-1.0, interest=0.0, principal_paid=0.0, balance=0.0)


def test_amortization_schedule_round_trips_through_json() -> None:
    schedule = amortize(principal=10_000.0, apr=0.06, term_months=12)
    serialised = schedule.model_dump(mode="json")
    revived = AmortizationSchedule.model_validate(serialised)
    assert revived.principal == schedule.principal
    assert revived.term_months == schedule.term_months
    assert math.isclose(revived.total_interest, schedule.total_interest, abs_tol=0.01)

"""Fixed + variable-rate loan amortization, plus dealer-fee unmasking.

A stated solar-loan APR ("4.99%, 25 years") often hides an embedded
dealer fee: the lender pays the installer ~15-25% of system cost up
front, and the homeowner pays it back inside the financed principal.
The *effective* real cost of capital is meaningfully higher than the
stated rate. `dealer_fee_effective_apr` solves for that effective rate
by PV-bisection so the audit's high-severity flag reports the real
number, not the marketing one.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AmortizationRow(BaseModel):
    month: int = Field(..., ge=1)
    payment: float = Field(..., ge=0.0)
    interest: float = Field(..., ge=0.0)
    principal_paid: float
    balance: float = Field(..., ge=0.0)


class AmortizationSchedule(BaseModel):
    principal: float
    apr: float | None = None  # None for variable-rate schedules
    term_months: int = Field(..., ge=1)
    rows: list[AmortizationRow]
    total_interest: float
    total_paid: float


def monthly_payment(principal: float, apr: float, term_months: int) -> float:
    """Standard mortgage formula. APR=0 → even principal split."""
    if principal <= 0.0:
        return 0.0
    if term_months <= 0:
        raise ValueError(f"term_months must be positive (got {term_months})")
    monthly_rate = apr / 12.0
    if abs(monthly_rate) < 1e-12:
        return principal / term_months
    factor = (1.0 + monthly_rate) ** term_months
    return principal * monthly_rate * factor / (factor - 1.0)


def amortize_variable(
    principal: float,
    monthly_rates: list[float],
) -> AmortizationSchedule:
    """Variable-rate amortization driven by one rate per month.

    Each month's payment is recomputed against the remaining balance and
    remaining term so the loan still closes on schedule as the rate
    moves. Real ARM products typically reset only at adjustment dates,
    but feeding a constant-rate list collapses to the fixed-rate case.
    """
    if principal < 0.0:
        raise ValueError("principal must be >= 0")
    if not monthly_rates:
        raise ValueError("monthly_rates must be non-empty")

    rows: list[AmortizationRow] = []
    balance = principal
    total_interest = 0.0
    n = len(monthly_rates)
    for m, rate in enumerate(monthly_rates, start=1):
        remaining = n - m + 1
        if abs(rate) < 1e-12:
            payment = balance / remaining
        else:
            factor = (1.0 + rate) ** remaining
            payment = balance * rate * factor / (factor - 1.0)
        interest = max(balance * rate, 0.0)
        principal_paid = payment - interest
        if m == n:
            # Squash floating-point residue on the last row so the
            # schedule closes at exactly zero.
            principal_paid = balance
            payment = principal_paid + interest
            balance = 0.0
        else:
            balance -= principal_paid
        total_interest += interest
        rows.append(
            AmortizationRow(
                month=m,
                payment=payment,
                interest=interest,
                principal_paid=principal_paid,
                balance=max(balance, 0.0),
            )
        )

    return AmortizationSchedule(
        principal=principal,
        apr=None,
        term_months=n,
        rows=rows,
        total_interest=total_interest,
        total_paid=principal + total_interest,
    )


def amortize(
    principal: float,
    apr: float,
    term_months: int,
) -> AmortizationSchedule:
    """Fixed-rate amortization. Thin wrapper over `amortize_variable`
    with a constant-rate list — the per-month payment recurrence is
    mathematically identical to the closed-form fixed-rate payment
    when the rate doesn't change."""
    if term_months <= 0:
        raise ValueError(f"term_months must be positive (got {term_months})")
    schedule = amortize_variable(principal, [apr / 12.0] * term_months)
    return schedule.model_copy(update={"apr": apr})


def dealer_fee_effective_apr(
    *,
    cash_price: float,
    stated_apr: float,
    dealer_fee_pct: float,
    term_months: int,
) -> float:
    """Back out the *effective* APR a homeowner is really paying.

    Solar lenders pay installers a 15-25% dealer fee that gets rolled
    into the financed principal. The homeowner sees ``stated_apr``;
    what they're actually paying is the rate at which the present value
    of their monthly payments equals the *cash* price (the real benefit
    received). Solved by bisection on the monthly rate — no SciPy.
    """
    if cash_price <= 0.0:
        raise ValueError("cash_price must be > 0")
    if not 0.0 <= dealer_fee_pct < 1.0:
        raise ValueError("dealer_fee_pct must be in [0, 1)")
    if term_months <= 0:
        raise ValueError("term_months must be > 0")

    financed = cash_price * (1.0 + dealer_fee_pct)
    payment = monthly_payment(financed, stated_apr, term_months)

    def pv_at_rate(monthly_rate: float) -> float:
        if abs(monthly_rate) < 1e-12:
            return payment * term_months
        return payment * (1.0 - (1.0 + monthly_rate) ** -term_months) / monthly_rate

    low = stated_apr / 12.0
    high = max(low * 4.0, 1.0)  # 100 %/mo upper bound is plenty
    if pv_at_rate(low) < cash_price:
        # Stated rate alone discounts payments below cash price — no
        # dealer fee at play.
        return stated_apr
    if pv_at_rate(high) > cash_price:
        # Degenerate input; return the upper-bracket annual rate.
        return high * 12.0

    pv_tolerance = 1e-9 * max(cash_price, 1.0)
    bracket_tolerance = 1e-12
    for _ in range(200):
        mid = (low + high) / 2.0
        if (high - low) < bracket_tolerance:
            return mid * 12.0
        pv_mid = pv_at_rate(mid)
        if abs(pv_mid - cash_price) < pv_tolerance:
            return mid * 12.0
        if pv_mid > cash_price:
            low = mid
        else:
            high = mid

    return ((low + high) / 2.0) * 12.0

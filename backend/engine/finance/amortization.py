"""Fixed + variable-rate loan amortization, plus dealer-fee unmasking.

A stated solar-loan APR ("4.99%, 25 years") often hides an embedded
dealer fee — the lender pays the installer, say, 18% of system cost up
front; the homeowner pays it back inside the financed principal. The
*effective* real cost of capital is meaningfully higher than the
stated rate. `dealer_fee_effective_apr` solves for that effective APR
so the audit's high-severity "dealer fee" flag reports a number with
teeth, not the marketing rate.

All formulas are textbook (Mort 101). The point of having them in
their own module is that golden-fixture tests can pin them and Monte
Carlo over them without weaving through the rest of the pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_NPV_TOLERANCE = 1e-9
DEFAULT_MAX_ITERATIONS = 200


class AmortizationRow(BaseModel):
    """One month of a loan schedule. `balance` is the *ending* balance
    after `payment` is applied."""

    month: int = Field(..., ge=1)
    payment: float = Field(..., ge=0.0)
    interest: float = Field(..., ge=0.0)
    principal_paid: float
    balance: float = Field(..., ge=0.0)


class AmortizationSchedule(BaseModel):
    """A complete loan schedule + summary."""

    principal: float
    apr: float | None = None  # None for variable-rate schedules
    term_months: int = Field(..., ge=1)
    rows: list[AmortizationRow]
    total_interest: float
    total_paid: float

    @property
    def monthly_payment_first(self) -> float:
        """First-month payment. Fixed-rate loans have a constant payment;
        variable-rate ones use the first month as a sanity reference."""
        return self.rows[0].payment if self.rows else 0.0


def monthly_payment(principal: float, apr: float, term_months: int) -> float:
    """Standard mortgage payment formula.

    `apr` is the annual rate (0.0499 for 4.99%); `term_months` is the
    number of monthly periods. APR of zero collapses to even principal."""
    if principal <= 0.0:
        return 0.0
    if term_months <= 0:
        raise ValueError(f"term_months must be positive (got {term_months})")
    monthly_rate = apr / 12.0
    if abs(monthly_rate) < 1e-12:
        return principal / term_months
    factor = (1.0 + monthly_rate) ** term_months
    return principal * monthly_rate * factor / (factor - 1.0)


def amortize(
    principal: float,
    apr: float,
    term_months: int,
) -> AmortizationSchedule:
    """Fixed-rate amortization. Returns a row per month.

    The final row's `balance` is exactly zero — any floating-point
    residual gets folded back into the last principal payment."""
    if principal < 0.0:
        raise ValueError("principal must be >= 0")
    payment = monthly_payment(principal, apr, term_months)
    monthly_rate = apr / 12.0

    rows: list[AmortizationRow] = []
    balance = principal
    total_interest = 0.0
    for m in range(1, term_months + 1):
        interest = max(balance * monthly_rate, 0.0)
        principal_paid = payment - interest
        # Squash float residue on the last row so the schedule closes cleanly.
        if m == term_months:
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
        apr=apr,
        term_months=term_months,
        rows=rows,
        total_interest=total_interest,
        total_paid=principal + total_interest,
    )


def amortize_variable(
    principal: float,
    monthly_rates: list[float],
) -> AmortizationSchedule:
    """Variable-rate amortization driven by a list of *monthly* rates.

    `monthly_rates` is a list of `apr / 12` style decimals — one entry
    per month of the schedule. The payment is recalculated each month
    against the remaining balance and remaining term so the loan still
    closes on schedule even as the rate moves. (Real ARM products
    typically reset only at adjustment dates; tests pin both behaviours.)
    """
    if principal < 0.0:
        raise ValueError("principal must be >= 0")
    if not monthly_rates:
        raise ValueError("monthly_rates must be non-empty")

    rows: list[AmortizationRow] = []
    balance = principal
    total_interest = 0.0
    for m, rate in enumerate(monthly_rates, start=1):
        remaining_periods = len(monthly_rates) - m + 1
        # Recompute payment against remaining balance + remaining term.
        if abs(rate) < 1e-12:
            payment = balance / remaining_periods
        else:
            factor = (1.0 + rate) ** remaining_periods
            payment = balance * rate * factor / (factor - 1.0)
        interest = max(balance * rate, 0.0)
        principal_paid = payment - interest
        if m == len(monthly_rates):
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
        term_months=len(monthly_rates),
        rows=rows,
        total_interest=total_interest,
        total_paid=principal + total_interest,
    )


def dealer_fee_effective_apr(
    *,
    cash_price: float,
    stated_apr: float,
    dealer_fee_pct: float,
    term_months: int,
) -> float:
    """Back out the *effective* APR a homeowner is really paying.

    Solar lenders pay installers a "dealer fee" — typically 15-25% of
    cash price — and the installer rolls that fee into the financed
    principal. The homeowner is told "4.99% APR for 25 years"; what
    they're actually paying is 4.99% on a principal that's
    `cash_price * (1 + dealer_fee_pct)`. The effective APR is the rate
    at which the discounted monthly payments equal the *cash* price.

    Solved by bisection on the monthly rate (no SciPy dependency).
    Returns the annualised effective rate (e.g. 0.13 for 13%).
    """
    if cash_price <= 0.0:
        raise ValueError("cash_price must be > 0")
    if not 0.0 <= dealer_fee_pct < 1.0:
        raise ValueError("dealer_fee_pct must be in [0, 1)")
    if term_months <= 0:
        raise ValueError("term_months must be > 0")

    # Total amount actually financed by the homeowner.
    financed = cash_price * (1.0 + dealer_fee_pct)
    payment = monthly_payment(financed, stated_apr, term_months)

    # Find the monthly rate `r` such that the present value of the
    # `term_months` × `payment` annuity equals the cash price (the
    # actual benefit received). Bisection over a wide bracket.
    def pv_at_rate(monthly_rate: float) -> float:
        if abs(monthly_rate) < 1e-12:
            return payment * term_months
        return payment * (1.0 - (1.0 + monthly_rate) ** -term_months) / monthly_rate

    low = stated_apr / 12.0
    high = max(low * 4.0, 1.0)  # 100%/mo upper bound is plenty
    pv_low = pv_at_rate(low)
    pv_high = pv_at_rate(high)
    if pv_low < cash_price:
        # Stated APR alone would already discount payments below the
        # cash price — that means there's no dealer fee at play.
        return stated_apr
    if pv_high > cash_price:
        # Even an absurd rate doesn't discount enough — caller passed
        # a degenerate scenario; return high as a safe upper bound.
        return high * 12.0

    for _ in range(DEFAULT_MAX_ITERATIONS):
        mid = (low + high) / 2.0
        pv_mid = pv_at_rate(mid)
        if abs(pv_mid - cash_price) < DEFAULT_NPV_TOLERANCE * max(cash_price, 1.0):
            return mid * 12.0
        if pv_mid > cash_price:
            low = mid
        else:
            high = mid

    return ((low + high) / 2.0) * 12.0

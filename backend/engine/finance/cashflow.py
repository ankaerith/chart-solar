"""Discounted cash-flow primitives: NPV, IRR, MIRR, discounted payback, LCOE.

These are the bones of the headline number on the audit. The user picks
a discount rate (HYSA, mortgage, S&P historical, the loan APR, or a
custom value) — everything else is mechanical. Implementations are
deterministic and SciPy-free: IRR runs Brent's method on NPV, MIRR is
closed-form, LCOE is a discounted-cost-over-discounted-energy ratio,
payback walks the cumulative discounted stream and interpolates the
crossing month.

All cashflows here are *annual*, sign-conventioned as the user
experiences them: negative for outflows (year-0 system cost, future
opex), positive for inflows (bill avoidance, SREC sales, NEM
true-ups). Year 0 is the first element. There is no separate "initial
investment" parameter — bake it into ``cashflows[0]``.
"""

from __future__ import annotations

import math

from backend.engine.finance._solver import _brent


def npv(discount_rate: float, cashflows: list[float]) -> float:
    """Net present value at ``discount_rate`` of an annual cashflow stream.

    Year 0 is undiscounted. ``discount_rate`` is annual; pass 0.06 for
    a 6 %/yr opportunity-cost rate. Negative rates are allowed (real
    rates on TIPS, for instance).
    """
    if not cashflows:
        raise ValueError("cashflows must be non-empty")
    if discount_rate <= -1.0:
        raise ValueError("discount_rate must be > -1.0")
    return sum(cf / (1.0 + discount_rate) ** t for t, cf in enumerate(cashflows))


def irr(cashflows: list[float], *, guess_low: float = -0.99, guess_high: float = 10.0) -> float:
    """Internal rate of return — the rate at which ``npv(rate, cashflows) == 0``.

    Brent's method on NPV (super-linear convergence; ~10–20 iterations
    vs ~200 for plain bisection at the same precision). No SciPy.
    Requires at least one sign change in the stream — a strictly-
    positive or strictly-negative stream has no finite IRR, and we
    raise so the caller doesn't silently quote a meaningless number
    on a stream that never breaks even.
    """
    if not cashflows:
        raise ValueError("cashflows must be non-empty")
    has_positive = any(cf > 0 for cf in cashflows)
    has_negative = any(cf < 0 for cf in cashflows)
    if not (has_positive and has_negative):
        raise ValueError("IRR requires at least one positive and one negative cashflow")

    npv_low = npv(guess_low, cashflows)
    npv_high = npv(guess_high, cashflows)
    if npv_low * npv_high > 0:
        raise ValueError(
            f"IRR not bracketed in [{guess_low}, {guess_high}]; "
            f"NPV is {npv_low:.4g} at low, {npv_high:.4g} at high"
        )

    return _brent(lambda r: npv(r, cashflows), guess_low, guess_high)


def mirr(
    cashflows: list[float],
    *,
    finance_rate: float,
    reinvest_rate: float,
) -> float:
    """Modified IRR: outflows discounted at ``finance_rate``, inflows
    compounded at ``reinvest_rate`` to the horizon.

    MIRR resolves the two pathologies plain IRR has: it can't be a
    multi-valued root on streams with multiple sign changes, and it
    doesn't implicitly assume positive cashflows are reinvested at the
    IRR itself (which is rarely realistic — a 12 % project IRR doesn't
    mean you actually have a 12 % reinvestment vehicle).
    """
    if len(cashflows) < 2:
        raise ValueError("cashflows must have at least 2 entries")
    if finance_rate <= -1.0 or reinvest_rate <= -1.0:
        raise ValueError("rates must be > -1.0")

    n = len(cashflows) - 1
    pv_outflows = 0.0
    fv_inflows = 0.0
    for t, cf in enumerate(cashflows):
        if cf < 0:
            pv_outflows += cf / (1.0 + finance_rate) ** t
        elif cf > 0:
            fv_inflows += cf * (1.0 + reinvest_rate) ** (n - t)
    if pv_outflows == 0 or fv_inflows == 0:
        raise ValueError("MIRR requires both positive and negative cashflows")
    return float((fv_inflows / -pv_outflows) ** (1.0 / n) - 1.0)


def discounted_payback_years(
    discount_rate: float,
    cashflows: list[float],
) -> float | None:
    """Years until the discounted cumulative cashflow turns positive.

    Linear-interpolates within the year that crosses zero — a payback
    of "9.4 years" is more useful than "9 or 10". Returns ``None`` when
    the stream never reaches break-even at this discount rate (the
    caller decides how to render that — typically "won't pay back at
    your chosen discount rate").
    """
    if not cashflows:
        raise ValueError("cashflows must be non-empty")
    if discount_rate <= -1.0:
        raise ValueError("discount_rate must be > -1.0")

    cumulative = 0.0
    for t, cf in enumerate(cashflows):
        previous_cumulative = cumulative
        year_increment = cf / (1.0 + discount_rate) ** t
        cumulative += year_increment
        if cumulative < 0:
            continue
        if t == 0:
            return 0.0
        fraction = -previous_cumulative / year_increment
        return float(t - 1) + fraction
    return None


def lcoe(
    *,
    capex: float,
    opex_per_year: list[float],
    energy_kwh_per_year: list[float],
    discount_rate: float,
) -> float:
    """Levelized cost of energy in $ per kWh.

    Standard NREL formula: PV(capex + opex stream) ÷ PV(energy stream).
    Both streams are discounted at the same rate; degradation is baked
    into ``energy_kwh_per_year`` by the caller (year 1 ≈ 99 %, year 25
    ≈ 87 %, etc — the exact curve is the degradation step's job).

    The crossover year — when LCOE equals the projected utility rate —
    is the headline number on the results screen. That's a UI render
    of two LCOE-versus-rate curves, not a separate function.
    """
    if capex < 0:
        raise ValueError("capex must be >= 0")
    if discount_rate <= -1.0:
        raise ValueError("discount_rate must be > -1.0")
    if len(opex_per_year) != len(energy_kwh_per_year):
        raise ValueError(
            f"opex_per_year ({len(opex_per_year)}) and "
            f"energy_kwh_per_year ({len(energy_kwh_per_year)}) must align"
        )
    if not opex_per_year:
        raise ValueError("at least one year of operation is required")

    pv_costs = capex + sum(
        op / (1.0 + discount_rate) ** (t + 1) for t, op in enumerate(opex_per_year)
    )
    pv_energy = sum(
        kwh / (1.0 + discount_rate) ** (t + 1) for t, kwh in enumerate(energy_kwh_per_year)
    )
    if pv_energy <= 0:
        raise ValueError("PV-discounted energy must be > 0")
    return pv_costs / pv_energy


def crossover_year(
    *,
    lcoe_per_kwh: float,
    starting_utility_rate_per_kwh: float,
    rate_escalation: float,
    horizon_years: int,
) -> int | None:
    """First year where the projected utility rate exceeds LCOE.

    The crossover year is the audit's headline framing: "your blended
    cost of solar electricity passes your utility's projected rate in
    year N". Returns the 1-indexed year, or ``None`` when the utility
    rate stays below LCOE across the entire horizon (rare but possible
    if the system is poorly sized or the utility is unusually cheap).
    """
    if lcoe_per_kwh < 0:
        raise ValueError("lcoe_per_kwh must be >= 0")
    if starting_utility_rate_per_kwh < 0:
        raise ValueError("starting_utility_rate_per_kwh must be >= 0")
    if rate_escalation <= -1.0:
        raise ValueError("rate_escalation must be > -1.0")
    if horizon_years < 1:
        raise ValueError("horizon_years must be >= 1")

    for year in range(1, horizon_years + 1):
        projected_rate = starting_utility_rate_per_kwh * (1.0 + rate_escalation) ** (year - 1)
        if projected_rate >= lcoe_per_kwh:
            return year
    return None


def annualized_return(
    cashflows: list[float],
    *,
    discount_rate: float,
) -> float:
    """Money-weighted annualized return from year-0 outflow + future inflows.

    Useful when the caller wants a simple "$X invested grew at Y %/yr
    on a present-value basis" framing without surfacing IRR. Computes
    the geometric mean growth rate of NPV-of-inflows over magnitude-of-
    outflows.
    """
    if not cashflows:
        raise ValueError("cashflows must be non-empty")
    n = len(cashflows) - 1
    if n < 1:
        raise ValueError("cashflows must span at least one year")
    pv_outflows = -sum(cf / (1.0 + discount_rate) ** t for t, cf in enumerate(cashflows) if cf < 0)
    pv_inflows = sum(cf / (1.0 + discount_rate) ** t for t, cf in enumerate(cashflows) if cf > 0)
    if pv_outflows <= 0:
        raise ValueError("annualized_return requires at least one negative cashflow")
    if pv_inflows <= 0:
        return -1.0
    ratio = pv_inflows / pv_outflows
    return math.pow(ratio, 1.0 / n) - 1.0

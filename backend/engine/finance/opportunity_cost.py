"""Opportunity-cost overlays for the cumulative-wealth chart.

A solar buyer's headline question isn't "is the project NPV positive?"
— it's "would the same dollars have done better elsewhere?" The
helpers here turn that question into per-year wealth streams that
the chart overlays directly on the solar cumulative-cashflow line.

Three baselines are commonly compared:

* **HYSA / cash equivalents** — typical rate ~4.5 %.
* **Mortgage paydown** — typical rate ~6 %, no compounding tax drag.
* **S&P 500 historical** — ~7 % real / ~10 % nominal long-run.

Custom overlays take a single annual-return number too. Tax
treatment is intentionally out of scope here (capital-gains drag on
S&P, mortgage-interest deduction, etc.) — the chart shows nominal
wealth and the user can apply their own after-tax view; surfacing a
half-modelled tax assumption would mislead more than it helps.

Pure deterministic, no IO. Sibling of :mod:`sale` — both expose
math primitives that the wizard threads into the results screen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalAllocationBaseline:
    """One labelled overlay line.

    ``annual_return`` is the *nominal* annual yield (HYSA APY, mortgage
    rate, S&P CAGR). Compounding is yearly — fine at chart resolution
    and sidesteps a 0/12-stub of monthly compounding for products that
    don't compound monthly. ``label`` lands in the chart legend.
    """

    label: str
    annual_return: float


HYSA_BASELINE = CapitalAllocationBaseline(label="HYSA 4.5%", annual_return=0.045)
MORTGAGE_PAYDOWN_BASELINE = CapitalAllocationBaseline(label="Mortgage 6%", annual_return=0.06)
SP500_BASELINE = CapitalAllocationBaseline(label="S&P 500 (~7%)", annual_return=0.07)


def alternative_wealth_path(
    *,
    initial_outlay: float,
    annual_return: float,
    hold_years: int,
) -> list[float]:
    """Year-by-year wealth of ``initial_outlay`` invested elsewhere.

    Returns a list of length ``hold_years + 1``. Index 0 is the
    initial outlay (positive — the wealth held in cash); index
    ``t`` is the wealth after ``t`` years of compounding at
    ``annual_return``. The first entry is intentionally
    ``+initial_outlay`` rather than ``-initial_outlay`` so the
    chart's overlay reads as wealth, not cashflow — the comparison
    point against the solar cumulative cashflow stream.

    Raises when ``hold_years`` is negative or ``initial_outlay`` is
    not finite — both are user-input boundary conditions worth
    failing loudly on.
    """
    if hold_years < 0:
        raise ValueError("hold_years must be >= 0")
    if not (initial_outlay == initial_outlay):  # NaN check
        raise ValueError("initial_outlay must be finite")
    return [initial_outlay * (1.0 + annual_return) ** t for t in range(hold_years + 1)]


def compare_npv_at_alternatives(
    *,
    cashflows: list[float],
    baselines: list[CapitalAllocationBaseline],
) -> dict[str, float]:
    """NPV of the solar cashflow stream at each alternative's rate.

    Treats each alternative's annual return as the discount rate;
    a positive NPV means solar beat the alternative on a same-dollars
    basis over the modelled hold. Returns a label → NPV map keyed
    on the baseline labels — order is preserved via Python dict
    insertion semantics so the chart can iterate in user-supplied
    order.
    """
    from backend.engine.finance.cashflow import npv

    return {b.label: npv(b.annual_return, cashflows) for b in baselines}


def cumulative_solar_wealth(*, cashflows: list[float]) -> list[float]:
    """Running cumulative cashflow — the solar wealth line on the chart.

    Year 0 is the initial outlay (negative on a cash buy); each
    subsequent year adds that year's net cashflow. The chart pairs
    this with the alternative-wealth paths above for the
    capital-allocation comparison.
    """
    out: list[float] = []
    running = 0.0
    for cf in cashflows:
        running += cf
        out.append(running)
    return out


__all__ = [
    "HYSA_BASELINE",
    "MORTGAGE_PAYDOWN_BASELINE",
    "SP500_BASELINE",
    "CapitalAllocationBaseline",
    "alternative_wealth_path",
    "compare_npv_at_alternatives",
    "cumulative_solar_wealth",
]

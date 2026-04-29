"""Year-over-year capacity-factor degradation.

Solar modules lose output over time. The conventional curve is a
year-1 step (typically 2 % from light-induced degradation + initial
ramp) followed by ~0.55 %/yr linear loss for the remaining warranty
term. Most manufacturer warranties quote the *linear* envelope (e.g.
"≥84.7 % at year 25"), so that's the default — but a geometric
(compounding) model is supported for sites where field data prefers it.

Output is a list of per-year *capacity factors* — multipliers between
0 and 1 that scale the year-1 energy yield. Year 1 is index 0.

The tornado sensitivity plot on the audit results screen reads from
this step: we surface the curve so the UI can sweep the annual loss
between, say, 0.4 % and 0.8 % and show the swing in 25-year cashflow.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DegradationModel = Literal["linear", "geometric"]

#: NREL field-study median for crystalline-silicon residential systems.
#: 0.55 %/yr is at the mild end; tornado sensitivity sweeps this.
DEFAULT_ANNUAL_LOSS: float = 0.0055

#: First-year light-induced degradation step. Manufacturer warranties
#: typically guarantee ≥98 % at year 1 (= 2 % loss).
DEFAULT_FIRST_YEAR_LOSS: float = 0.02


class DegradationCurve(BaseModel):
    """Per-year capacity factors over the analysis horizon.

    ``factors[0]`` is year 1, ``factors[-1]`` is year ``years``. Values
    are dimensionless multipliers in [0, 1] applied to the undegraded
    annual energy yield.
    """

    model: DegradationModel
    first_year_loss: float = Field(..., ge=0.0, lt=1.0)
    annual_loss: float = Field(..., ge=0.0, lt=1.0)
    years: int = Field(..., ge=1)
    factors: list[float] = Field(..., min_length=1)


def degradation_factors(
    *,
    years: int,
    first_year_loss: float = DEFAULT_FIRST_YEAR_LOSS,
    annual_loss: float = DEFAULT_ANNUAL_LOSS,
    model: DegradationModel = "linear",
) -> DegradationCurve:
    """Build the per-year capacity-factor curve.

    ``linear`` is the manufacturer-warranty convention: subtract
    ``annual_loss`` once per year past year 1 from the year-1 factor.
    ``geometric`` compounds the same rate, which is what NREL field
    studies typically report — the two diverge by ~2 % over 25 years
    at 0.55 %/yr.

    Negative factors are clamped to zero (in case a poorly-chosen
    annual_loss × years would push the curve below zero — caller's
    bug, but we don't want NPV to silently consume negative energy).
    """
    if years < 1:
        raise ValueError("years must be >= 1")
    if not 0.0 <= first_year_loss < 1.0:
        raise ValueError("first_year_loss must be in [0, 1)")
    if not 0.0 <= annual_loss < 1.0:
        raise ValueError("annual_loss must be in [0, 1)")

    year_one_factor = 1.0 - first_year_loss

    factors: list[float]
    if model == "linear":
        factors = [max(0.0, year_one_factor - annual_loss * t) for t in range(years)]
    elif model == "geometric":
        factors = [max(0.0, year_one_factor * (1.0 - annual_loss) ** t) for t in range(years)]
    else:
        raise ValueError(f"unknown degradation model: {model!r}")

    return DegradationCurve(
        model=model,
        first_year_loss=first_year_loss,
        annual_loss=annual_loss,
        years=years,
        factors=factors,
    )


def apply_degradation(year_one_kwh: float, curve: DegradationCurve) -> list[float]:
    """Year-1 energy × per-year factor → per-year energy.

    Used by the finance step's cashflow construction: per-year energy
    drives per-year bill avoidance, which drives NPV / IRR / payback.
    """
    if year_one_kwh < 0:
        raise ValueError("year_one_kwh must be >= 0")
    return [year_one_kwh * f for f in curve.factors]


def warranty_endpoint(curve: DegradationCurve) -> float:
    """Capacity factor at the final year of the curve.

    Useful for sanity-checking against vendor warranties: a Tier-1
    crystalline-Si module typically guarantees ≥84 % at year 25, and
    the default curve here lands at ~85 %.
    """
    return curve.factors[-1]

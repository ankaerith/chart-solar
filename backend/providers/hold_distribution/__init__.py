"""HoldDistributionProvider port — sale-year prior keyed on ZIP.

The sale-scenario math (``backend.engine.finance.sale.expected_sale_npv``)
weights NPV across a discrete distribution over candidate sale years.
Most homeowners can't supply that distribution off the top of their
head, so the wizard reads a default from this provider and lets the
user override either the central tendency (median hold years) or the
full curve.

The launch-day adapter is the national default: a discrete Gaussian
centered on ~13-year median home tenure (American Community Survey
2022 median for owner-occupied units) with σ = 5 years, bracketed to
the model horizon. A future ZIP-keyed ACS adapter slots into the same
Protocol — its provenance becomes the seed file rather than a constant.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from backend.engine.finance.sale import HoldYearProbability

#: ACS 2022 median owner-occupied tenure (rounded). Source: U.S. Census
#: Bureau, "Length of time householders have lived in unit".
DEFAULT_MEDIAN_HOLD_YEARS = 13

#: σ = 5 puts ~68 % of mass between years 8 and 18.
DEFAULT_HOLD_SIGMA_YEARS = 5.0

#: ``HoldYearProbability`` rejects year > 40; most engine horizons stop at 30.
DEFAULT_HORIZON_YEARS = 30


class HoldDistributionQuery(BaseModel):
    """Lookup parameters for a hold-year prior.

    The country code is explicit so a UK ZIP-equivalent (post code)
    routes to a different default than a US ZIP — the LBNL-driven
    default below is calibrated against US Census data.
    """

    country: str = Field(..., min_length=2, max_length=2)
    zip_code: str | None = None
    horizon_years: int = Field(DEFAULT_HORIZON_YEARS, ge=2, le=40)


@runtime_checkable
class HoldDistributionProvider(Protocol):
    """Return the prior distribution over candidate sale years."""

    name: str

    async def fetch(self, query: HoldDistributionQuery) -> list[HoldYearProbability]: ...


def discrete_gaussian_distribution(
    *,
    median_years: int,
    sigma_years: float,
    horizon_years: int,
) -> list[HoldYearProbability]:
    """Discrete-Gaussian PMF over years 1..horizon, normalized to sum=1.

    The continuous Gaussian is sampled at each integer year, then the
    raw weights are renormalized so the truncation at ``[1, horizon]``
    leaves a proper distribution. Year 0 is excluded — a sale at
    closing isn't a hold scenario.
    """
    if median_years < 1:
        raise ValueError("median_years must be >= 1")
    if sigma_years <= 0:
        raise ValueError("sigma_years must be > 0")
    if horizon_years < 2:
        raise ValueError("horizon_years must be >= 2")

    raw = [
        math.exp(-0.5 * ((year - median_years) / sigma_years) ** 2)
        for year in range(1, horizon_years + 1)
    ]
    total = sum(raw)
    return [
        HoldYearProbability(year=year, probability=weight / total)
        for year, weight in zip(range(1, horizon_years + 1), raw, strict=True)
    ]


__all__ = [
    "DEFAULT_HOLD_SIGMA_YEARS",
    "DEFAULT_HORIZON_YEARS",
    "DEFAULT_MEDIAN_HOLD_YEARS",
    "HoldDistributionProvider",
    "HoldDistributionQuery",
    "discrete_gaussian_distribution",
]

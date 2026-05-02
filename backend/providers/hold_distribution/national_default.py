"""National-default hold-distribution provider.

Returns the same discrete-Gaussian distribution for every ZIP — a
launch-day approximation while a per-ZIP ACS adapter is out of scope.
The wizard's user-override flow takes precedence over whatever this
returns, so a homeowner who knows they plan to sell at year 7 isn't
forced to live with the median.
"""

from __future__ import annotations

from backend.engine.finance.sale import HoldYearProbability
from backend.providers.hold_distribution import (
    DEFAULT_HOLD_SIGMA_YEARS,
    DEFAULT_MEDIAN_HOLD_YEARS,
    HoldDistributionQuery,
    discrete_gaussian_distribution,
)


class NationalDefaultHoldDistributionProvider:
    """ZIP-blind provider that returns the national-default Gaussian.

    Implements ``HoldDistributionProvider``. Construct with custom
    ``median_years`` / ``sigma_years`` for tests or sensitivity sweeps;
    production callers stick with the ACS-derived defaults.
    """

    name = "national_default"

    def __init__(
        self,
        *,
        median_years: int = DEFAULT_MEDIAN_HOLD_YEARS,
        sigma_years: float = DEFAULT_HOLD_SIGMA_YEARS,
    ) -> None:
        self._median_years = median_years
        self._sigma_years = sigma_years

    async def fetch(self, query: HoldDistributionQuery) -> list[HoldYearProbability]:
        return discrete_gaussian_distribution(
            median_years=self._median_years,
            sigma_years=self._sigma_years,
            horizon_years=query.horizon_years,
        )


__all__ = ["NationalDefaultHoldDistributionProvider"]

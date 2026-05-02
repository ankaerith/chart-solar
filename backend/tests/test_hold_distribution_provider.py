"""HoldDistributionProvider — national-default + discrete-Gaussian builder.

Covers the math primitive (truncation-aware normalization, central
tendency, σ spread) plus the launch-day provider's contract: any
query returns the same Gaussian, and the result drops cleanly into
``SaleScenarioInputs`` without re-normalization.
"""

from __future__ import annotations

import pytest

from backend.domain.hold import SaleScenarioInputs
from backend.engine.finance.sale import expected_sale_npv
from backend.providers.hold_distribution import (
    DEFAULT_HOLD_SIGMA_YEARS,
    DEFAULT_HORIZON_YEARS,
    DEFAULT_MEDIAN_HOLD_YEARS,
    HoldDistributionProvider,
    HoldDistributionQuery,
    discrete_gaussian_distribution,
)
from backend.providers.hold_distribution.national_default import (
    NationalDefaultHoldDistributionProvider,
)


def test_discrete_gaussian_normalizes_to_one() -> None:
    dist = discrete_gaussian_distribution(
        median_years=DEFAULT_MEDIAN_HOLD_YEARS,
        sigma_years=DEFAULT_HOLD_SIGMA_YEARS,
        horizon_years=DEFAULT_HORIZON_YEARS,
    )
    total = sum(p.probability for p in dist)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_discrete_gaussian_peaks_at_median() -> None:
    dist = discrete_gaussian_distribution(
        median_years=13,
        sigma_years=5.0,
        horizon_years=30,
    )
    by_year = {p.year: p.probability for p in dist}
    peak_year = max(by_year, key=lambda y: by_year[y])
    assert peak_year == 13


def test_discrete_gaussian_covers_every_year_in_horizon() -> None:
    """Truncation drops year 0 but every year 1..horizon must be present."""
    dist = discrete_gaussian_distribution(
        median_years=13,
        sigma_years=5.0,
        horizon_years=30,
    )
    years = [p.year for p in dist]
    assert years == list(range(1, 31))


def test_discrete_gaussian_symmetric_around_median() -> None:
    """Years equidistant from the median get equal mass when both lie
    within the horizon — verifies the truncation isn't biasing one side."""
    dist = discrete_gaussian_distribution(
        median_years=15,
        sigma_years=5.0,
        horizon_years=30,
    )
    by_year = {p.year: p.probability for p in dist}
    assert by_year[10] == pytest.approx(by_year[20])
    assert by_year[12] == pytest.approx(by_year[18])


def test_smaller_sigma_concentrates_mass() -> None:
    """A tighter σ pushes more probability onto the median year."""
    tight = discrete_gaussian_distribution(median_years=13, sigma_years=2.0, horizon_years=30)
    wide = discrete_gaussian_distribution(median_years=13, sigma_years=8.0, horizon_years=30)
    tight_peak = next(p for p in tight if p.year == 13).probability
    wide_peak = next(p for p in wide if p.year == 13).probability
    assert tight_peak > wide_peak


def test_discrete_gaussian_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="median_years"):
        discrete_gaussian_distribution(median_years=0, sigma_years=5.0, horizon_years=30)
    with pytest.raises(ValueError, match="sigma_years"):
        discrete_gaussian_distribution(median_years=13, sigma_years=0.0, horizon_years=30)
    with pytest.raises(ValueError, match="horizon_years"):
        discrete_gaussian_distribution(median_years=13, sigma_years=5.0, horizon_years=1)


async def test_national_default_provider_returns_gaussian() -> None:
    provider = NationalDefaultHoldDistributionProvider()
    query = HoldDistributionQuery(country="US", zip_code="94110")
    result = await provider.fetch(query)
    expected = discrete_gaussian_distribution(
        median_years=DEFAULT_MEDIAN_HOLD_YEARS,
        sigma_years=DEFAULT_HOLD_SIGMA_YEARS,
        horizon_years=DEFAULT_HORIZON_YEARS,
    )
    assert result == expected


async def test_national_default_provider_is_zip_blind() -> None:
    """Launch-day adapter ignores ZIP — every query returns the same
    distribution. A future ACS adapter will replace this provider; the
    test exists so a regression is loud."""
    provider = NationalDefaultHoldDistributionProvider()
    a = await provider.fetch(HoldDistributionQuery(country="US", zip_code="10001"))
    b = await provider.fetch(HoldDistributionQuery(country="US", zip_code="94110"))
    assert a == b


async def test_national_default_honours_horizon_query_param() -> None:
    """Passing a shorter horizon trims + renormalizes."""
    provider = NationalDefaultHoldDistributionProvider()
    short = await provider.fetch(
        HoldDistributionQuery(country="US", zip_code="94110", horizon_years=20)
    )
    assert {p.year for p in short} == set(range(1, 21))
    assert sum(p.probability for p in short) == pytest.approx(1.0, abs=1e-9)


async def test_national_default_accepts_custom_calibration() -> None:
    """Tests / sensitivity sweeps can override median + σ."""
    provider = NationalDefaultHoldDistributionProvider(median_years=7, sigma_years=2.0)
    result = await provider.fetch(HoldDistributionQuery(country="US"))
    by_year = {p.year: p.probability for p in result}
    peak_year = max(by_year, key=lambda y: by_year[y])
    assert peak_year == 7


async def test_national_default_feeds_expected_sale_npv() -> None:
    """Provider output drives a real ``expected_sale_npv`` call —
    smoke-tests the integration shape, not the financial output."""
    provider = NationalDefaultHoldDistributionProvider()
    distribution = await provider.fetch(HoldDistributionQuery(country="US", horizon_years=20))
    inputs = SaleScenarioInputs(hold_year_probabilities=distribution)
    cashflows = [-30_000.0] + [3_000.0] * 25
    result = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=8.0,
        inputs=inputs,
    )
    assert len(result.outcomes) == len(distribution)


def test_provider_satisfies_protocol() -> None:
    provider = NationalDefaultHoldDistributionProvider()
    assert isinstance(provider, HoldDistributionProvider)

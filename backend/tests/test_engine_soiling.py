"""Monthly soiling loss curve — pure-math.

Tests pin the climate-band defaults so a future tweak to the
constants doesn't silently shift annual-average derate by more than
the tolerance the audit's headline number can absorb.
"""

from __future__ import annotations

import pytest

from backend.engine.steps.soiling import (
    ARID_FACTORS,
    CLIMATE_BAND_FACTORS,
    TEMPERATE_FACTORS,
    TROPICAL_FACTORS,
    SoilingCurve,
    apply_monthly_soiling,
    climate_band_for_latitude,
    soiling_curve,
)


def test_temperate_curve_avg_in_published_band() -> None:
    """NREL field-study median for temperate residential: 1-2 % derate.
    Avg factor = 1 - derate, so the band is [0.98, 0.99]."""
    curve = soiling_curve(climate_band="temperate")
    assert 0.98 <= curve.annual_avg_factor <= 0.99


def test_arid_curve_avg_at_published_dry_climate_loss() -> None:
    """Arid climates lose 5-8 % annually per Mejia & Kleissl 2013."""
    curve = soiling_curve(climate_band="arid")
    assert 0.92 <= curve.annual_avg_factor <= 0.96


def test_tropical_curve_lowest_loss_of_three_bands() -> None:
    """Tropical climates self-clean via frequent rain — should be the
    lightest soiling of the three bands."""
    temperate = soiling_curve(climate_band="temperate").annual_avg_factor
    arid = soiling_curve(climate_band="arid").annual_avg_factor
    tropical = soiling_curve(climate_band="tropical").annual_avg_factor
    assert tropical >= temperate
    assert temperate > arid


def test_arid_summer_months_lower_than_winter() -> None:
    """Arid zones accumulate dust through dry summers — June-August
    should be the worst months."""
    curve = soiling_curve(climate_band="arid")
    summer_avg = sum(curve.monthly_factors[5:8]) / 3.0  # Jun-Aug
    winter_avg = (
        curve.monthly_factors[11] + curve.monthly_factors[0] + curve.monthly_factors[1]
    ) / 3.0  # Dec-Feb
    assert summer_avg < winter_avg


def test_climate_band_for_latitude_tropical_below_23_5() -> None:
    assert climate_band_for_latitude(0.0) == "tropical"
    assert climate_band_for_latitude(15.0) == "tropical"
    assert climate_band_for_latitude(-20.0) == "tropical"


def test_climate_band_for_latitude_temperate_outside_tropics() -> None:
    assert climate_band_for_latitude(35.0) == "temperate"
    assert climate_band_for_latitude(51.5) == "temperate"  # London
    assert climate_band_for_latitude(-45.0) == "temperate"


def test_dry_climate_flag_overrides_latitude() -> None:
    assert climate_band_for_latitude(33.0, dry_climate=True) == "arid"
    assert climate_band_for_latitude(15.0, dry_climate=True) == "arid"


def test_custom_factors_accepted() -> None:
    custom = [0.99] * 12
    curve = soiling_curve(climate_band="temperate", monthly_factors=custom)
    assert curve.monthly_factors == custom
    assert curve.annual_avg_factor == pytest.approx(0.99)


def test_custom_factors_must_be_12_long() -> None:
    with pytest.raises(ValueError, match="exactly 12"):
        soiling_curve(monthly_factors=[0.99] * 11)


def test_custom_factors_must_be_in_unit_interval() -> None:
    with pytest.raises(ValueError, match="must be in"):
        soiling_curve(monthly_factors=[1.05] * 12)
    with pytest.raises(ValueError, match="must be in"):
        soiling_curve(monthly_factors=[0.0] * 12)


def test_apply_monthly_soiling_to_constant_hourly_array() -> None:
    """A flat 1 kWh/h array projected through the temperate curve
    should integrate to (8760 × annual_avg_factor)."""
    curve = soiling_curve(climate_band="temperate")
    hourly = [1.0] * 8760
    derated = apply_monthly_soiling(hourly_kwh=hourly, curve=curve)
    total = sum(derated)
    expected = 8760 * curve.annual_avg_factor
    # Allow some tolerance because hours-per-month differ — Jan and Mar
    # have 744 hours but Feb has 672, so the *time-weighted* average
    # diverges slightly from the simple monthly factor average.
    assert total == pytest.approx(expected, rel=0.005)


def test_apply_monthly_soiling_first_january_hour_uses_january_factor() -> None:
    curve = soiling_curve(climate_band="arid")
    hourly = [1.0] * 8760
    derated = apply_monthly_soiling(hourly_kwh=hourly, curve=curve)
    assert derated[0] == pytest.approx(curve.monthly_factors[0])


def test_apply_monthly_soiling_last_hour_uses_december_factor() -> None:
    curve = soiling_curve(climate_band="arid")
    hourly = [1.0] * 8760
    derated = apply_monthly_soiling(hourly_kwh=hourly, curve=curve)
    assert derated[-1] == pytest.approx(curve.monthly_factors[11])


def test_apply_monthly_soiling_rejects_misaligned_inputs() -> None:
    curve = soiling_curve()
    with pytest.raises(ValueError, match="must match"):
        apply_monthly_soiling(hourly_kwh=[1.0] * 100, curve=curve)


def test_climate_band_factors_keys_match_literal_type() -> None:
    """Ensure every ClimateBand has a registered factors tuple."""
    assert set(CLIMATE_BAND_FACTORS) == {"temperate", "arid", "tropical"}


def test_constant_factor_tuples_have_12_entries() -> None:
    assert len(TEMPERATE_FACTORS) == 12
    assert len(ARID_FACTORS) == 12
    assert len(TROPICAL_FACTORS) == 12


def test_curve_round_trips_through_json() -> None:
    curve = soiling_curve(climate_band="arid")
    payload = curve.model_dump(mode="json")
    revived = SoilingCurve.model_validate(payload)
    assert revived.climate_band == curve.climate_band
    assert revived.monthly_factors == curve.monthly_factors

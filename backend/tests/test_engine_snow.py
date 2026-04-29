"""Snow loss model — pure-math, lat + tilt dependent.

The lat-band loss tables and tilt-shed function are empirical
envelopes (Marion et al. 2013, Townsend); these tests pin the
behaviour against named reference cities so the audit's snow-loss
numbers don't drift silently when the constants are tweaked.
"""

from __future__ import annotations

import pytest

from backend.engine.steps.snow import (
    DEFAULT_SNOW_THRESHOLD_LAT,
    LAT_BAND_LOSS_FRACTIONS,
    NATURAL_SHED_TILT_DEG,
    SnowLossCurve,
    apply_monthly_snow_loss,
    snow_loss_curve,
)


def test_phoenix_no_snow_loss() -> None:
    """Phoenix at 33.4° N is below the snow threshold — all factors
    should be exactly 1.0."""
    curve = snow_loss_curve(lat=33.4, tilt_deg=25.0)
    assert curve.band == "no-snow"
    assert all(f == 1.0 for f in curve.monthly_factors)
    assert curve.annual_avg_factor == pytest.approx(1.0)


def test_atlanta_no_snow_loss() -> None:
    """Atlanta at 33.7° N — sub-threshold."""
    curve = snow_loss_curve(lat=33.7, tilt_deg=25.0)
    assert all(f == 1.0 for f in curve.monthly_factors)


def test_boulder_temperate_winter_band() -> None:
    """Boulder at 40.0° N → temperate-winter (35-45°)."""
    curve = snow_loss_curve(lat=40.0, tilt_deg=25.0)
    assert curve.band == "temperate-winter"
    # Summer months are no-loss
    for month_idx in (5, 6, 7, 8):  # Jun-Sep
        assert curve.monthly_factors[month_idx] == pytest.approx(1.0)
    # Winter months take a hit
    assert curve.monthly_factors[0] < 1.0  # Jan
    assert curve.monthly_factors[11] < 1.0  # Dec


def test_minneapolis_cold_winter_band() -> None:
    """Minneapolis at 45.0° N → cold-winter (45-55°). The boundary
    rule is `< 55`, `>= 45`."""
    curve = snow_loss_curve(lat=45.0, tilt_deg=25.0)
    assert curve.band == "cold-winter"


def test_anchorage_subarctic_band() -> None:
    """Anchorage at 61.2° N → subarctic (>55°)."""
    curve = snow_loss_curve(lat=61.2, tilt_deg=25.0)
    assert curve.band == "subarctic"
    # January should be the harshest — at least 25 % loss at flat tilt
    assert curve.monthly_factors[0] < 0.75


def test_higher_latitude_loses_more() -> None:
    """At equal tilt, snow-loss should be monotone-increasing in
    latitude across the bands."""
    boulder = snow_loss_curve(lat=40.0, tilt_deg=25.0)
    minneapolis = snow_loss_curve(lat=45.0, tilt_deg=25.0)
    anchorage = snow_loss_curve(lat=61.2, tilt_deg=25.0)
    assert boulder.annual_avg_factor > minneapolis.annual_avg_factor
    assert minneapolis.annual_avg_factor > anchorage.annual_avg_factor


def test_southern_hemisphere_uses_absolute_latitude() -> None:
    """Christchurch NZ at -43.5° should still hit a snow-loss band,
    even though we don't (yet) shift the monthly distribution by
    six months. Documented limitation; pinned here so the bug is
    visible if anyone tries to "fix" the abs-lat shortcut without
    fixing the seasonal shift first."""
    christchurch = snow_loss_curve(lat=-43.5, tilt_deg=25.0)
    assert christchurch.band == "temperate-winter"


def test_steep_tilt_sheds_more_snow() -> None:
    """Same lat, steeper tilt → less snow loss. 45° tilt cuts loss
    in half (the shedding factor caps at 0.5)."""
    flat = snow_loss_curve(lat=45.0, tilt_deg=15.0)
    steep = snow_loss_curve(lat=45.0, tilt_deg=45.0)
    flat_loss = 1.0 - flat.annual_avg_factor
    steep_loss = 1.0 - steep.annual_avg_factor
    assert steep_loss == pytest.approx(flat_loss * 0.5, rel=0.05)


def test_tilt_below_25_no_shedding_benefit() -> None:
    flat25 = snow_loss_curve(lat=45.0, tilt_deg=25.0)
    flat15 = snow_loss_curve(lat=45.0, tilt_deg=15.0)
    assert flat25.annual_avg_factor == pytest.approx(flat15.annual_avg_factor)


def test_tilt_above_natural_shed_caps_at_half_loss() -> None:
    """A 60° tilt doesn't give *more* shedding than 40° — cap at 0.5."""
    at_40 = snow_loss_curve(lat=45.0, tilt_deg=40.0)
    at_60 = snow_loss_curve(lat=45.0, tilt_deg=60.0)
    assert at_40.annual_avg_factor == pytest.approx(at_60.annual_avg_factor)


def test_tilt_25_to_40_interpolates_linearly() -> None:
    flat = snow_loss_curve(lat=45.0, tilt_deg=25.0)
    mid = snow_loss_curve(lat=45.0, tilt_deg=32.5)  # halfway
    steep = snow_loss_curve(lat=45.0, tilt_deg=40.0)
    flat_loss = 1.0 - flat.annual_avg_factor
    steep_loss = 1.0 - steep.annual_avg_factor
    mid_loss = 1.0 - mid.annual_avg_factor
    expected_mid = (flat_loss + steep_loss) / 2.0
    assert mid_loss == pytest.approx(expected_mid, rel=0.01)


def test_custom_threshold_excludes_marginal_lat() -> None:
    """Caller can push the threshold up (e.g. require 40° before
    we apply snow loss)."""
    curve = snow_loss_curve(lat=37.0, tilt_deg=25.0, snow_threshold_lat=40.0)
    assert all(f == 1.0 for f in curve.monthly_factors)


def test_apply_monthly_snow_loss_to_constant_array() -> None:
    """Flat 1 kWh/h projected through the snow curve → time-weighted
    average across months, close to the simple average."""
    curve = snow_loss_curve(lat=40.0, tilt_deg=25.0)
    hourly = [1.0] * 8760
    derated = apply_monthly_snow_loss(hourly_kwh=hourly, curve=curve)
    assert sum(derated) == pytest.approx(8760 * curve.annual_avg_factor, rel=0.005)


def test_apply_monthly_snow_loss_january_uses_january_factor() -> None:
    curve = snow_loss_curve(lat=45.0, tilt_deg=25.0)
    hourly = [1.0] * 8760
    derated = apply_monthly_snow_loss(hourly_kwh=hourly, curve=curve)
    assert derated[0] == pytest.approx(curve.monthly_factors[0])


def test_apply_monthly_snow_loss_rejects_misaligned_inputs() -> None:
    curve = snow_loss_curve(lat=45.0, tilt_deg=25.0)
    with pytest.raises(ValueError, match="must match"):
        apply_monthly_snow_loss(hourly_kwh=[1.0] * 100, curve=curve)


def test_lat_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="lat must be in"):
        snow_loss_curve(lat=100.0, tilt_deg=25.0)


def test_tilt_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="tilt_deg must be in"):
        snow_loss_curve(lat=45.0, tilt_deg=-5.0)


def test_default_threshold_pinned() -> None:
    assert DEFAULT_SNOW_THRESHOLD_LAT == pytest.approx(35.0)


def test_natural_shed_tilt_pinned() -> None:
    assert NATURAL_SHED_TILT_DEG == pytest.approx(40.0)


def test_lat_band_table_has_three_bands_each_12_long() -> None:
    assert set(LAT_BAND_LOSS_FRACTIONS) == {
        "temperate-winter",
        "cold-winter",
        "subarctic",
    }
    for band, losses in LAT_BAND_LOSS_FRACTIONS.items():
        assert len(losses) == 12, f"{band} has {len(losses)} entries"
        for loss in losses:
            assert 0.0 <= loss <= 1.0


def test_curve_round_trips_through_json() -> None:
    curve = snow_loss_curve(lat=45.0, tilt_deg=30.0)
    payload = curve.model_dump(mode="json")
    revived = SnowLossCurve.model_validate(payload)
    assert revived.band == curve.band
    assert revived.monthly_factors == curve.monthly_factors

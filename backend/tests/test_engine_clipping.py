"""DC:AC inverter clipping — pure-math modifier.

These tests construct synthetic hourly DC arrays so they don't
depend on the dc_production step landing first. The kWh accounting
is the audit's headline number for over-aggressive inverter sizing,
so we pin the loss math against hand-computed expectations.
"""

from __future__ import annotations

import pytest

from backend.engine.steps.clipping import (
    AGGRESSIVE_RATIO_THRESHOLD,
    DEFAULT_INVERTER_EFFICIENCY,
    ClippingResult,
    apply_clipping,
)


def _midday_curve(peak_dc_kw: float, hours: int = 24) -> list[float]:
    """Crude bell-shape DC curve peaking at noon — sufficient for
    clipping logic, no claim of physical accuracy."""
    out: list[float] = []
    for h in range(hours):
        if 6 <= h <= 18:
            # Triangle: 0 at 6, peak at 12, 0 at 18
            distance_from_noon = abs(h - 12)
            factor = max(0.0, 1.0 - distance_from_noon / 6.0)
            out.append(peak_dc_kw * factor)
        else:
            out.append(0.0)
    return out


def test_no_clipping_when_dc_never_exceeds_ac() -> None:
    """At a 1.0 DC:AC ratio with η=1, AC is just DC."""
    dc = _midday_curve(peak_dc_kw=5.0)
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=8.0,
        inverter_efficiency=1.0,
        dc_kw_nameplate=5.0,
    )
    assert result.clipped_hours == 0
    assert result.clipping_loss_kwh == pytest.approx(0.0)
    assert result.hourly_ac_kw == dc


def test_efficiency_applied_below_clipping_threshold() -> None:
    dc = [4.0, 4.0]
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=8.0,
        inverter_efficiency=0.96,
        dc_kw_nameplate=4.0,
    )
    for ac in result.hourly_ac_kw:
        assert ac == pytest.approx(4.0 * 0.96)


def test_clips_at_inverter_nameplate() -> None:
    """Aggressive 1.6× ratio: peak DC × η is way past inverter cap."""
    dc = _midday_curve(peak_dc_kw=8.0)
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0,
        inverter_efficiency=1.0,
        dc_kw_nameplate=8.0,
    )
    assert max(result.hourly_ac_kw) == pytest.approx(5.0)
    assert result.clipped_hours > 0


def test_clipping_loss_kwh_matches_hand_computed() -> None:
    """Three hours of 8 kW DC at η=1 with a 5 kW inverter: each clipped
    hour loses 3 kW × 1 h = 3 kWh. Verifies the running-sum is right."""
    dc = [8.0, 8.0, 8.0]
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0,
        inverter_efficiency=1.0,
        dc_kw_nameplate=8.0,
    )
    assert result.clipped_hours == 3
    assert result.clipping_loss_kwh == pytest.approx(9.0)


def test_partial_hour_at_threshold_does_not_count_as_clipped() -> None:
    """Exactly equal to the cap is not clipping — the ``>`` strict
    threshold is what the loss math depends on."""
    dc = [5.0, 5.0]
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0,
        inverter_efficiency=1.0,
        dc_kw_nameplate=5.0,
    )
    assert result.clipped_hours == 0
    assert result.clipping_loss_kwh == pytest.approx(0.0)


def test_aggressive_ratio_flag_above_threshold() -> None:
    dc = [5.0]
    high = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0 / 1.4,  # ratio = 1.4
        dc_kw_nameplate=5.0,
    )
    low = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0 / 1.2,  # ratio = 1.2
        dc_kw_nameplate=5.0,
    )
    assert high.is_aggressive_ratio is True
    assert low.is_aggressive_ratio is False
    assert high.dc_ac_ratio > AGGRESSIVE_RATIO_THRESHOLD
    assert low.dc_ac_ratio < AGGRESSIVE_RATIO_THRESHOLD


def test_dc_ac_ratio_uses_max_dc_when_nameplate_omitted() -> None:
    """When the caller only has a derated array, the proxy ratio uses
    peak hourly DC as the numerator."""
    dc = [0.0, 4.0, 7.0, 4.0, 0.0]
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0,
        inverter_efficiency=1.0,
    )
    assert result.dc_ac_ratio == pytest.approx(7.0 / 5.0)


def test_default_inverter_efficiency_is_industry_typical() -> None:
    assert 0.95 <= DEFAULT_INVERTER_EFFICIENCY <= 0.98


def test_default_aggressive_threshold_matches_audit_flag() -> None:
    assert AGGRESSIVE_RATIO_THRESHOLD == pytest.approx(1.30)


def test_rejects_zero_inverter() -> None:
    with pytest.raises(ValueError, match="inverter_ac_kw must be > 0"):
        apply_clipping(hourly_dc_kw=[1.0], inverter_ac_kw=0.0, dc_kw_nameplate=1.0)


def test_rejects_invalid_efficiency() -> None:
    with pytest.raises(ValueError, match="inverter_efficiency must be in"):
        apply_clipping(
            hourly_dc_kw=[1.0],
            inverter_ac_kw=1.0,
            inverter_efficiency=1.5,
            dc_kw_nameplate=1.0,
        )


def test_rejects_empty_dc() -> None:
    with pytest.raises(ValueError, match="must be non-empty"):
        apply_clipping(hourly_dc_kw=[], inverter_ac_kw=1.0, dc_kw_nameplate=1.0)


def test_rejects_negative_dc_entry() -> None:
    with pytest.raises(ValueError, match="entries must be >= 0"):
        apply_clipping(
            hourly_dc_kw=[1.0, -0.5],
            inverter_ac_kw=1.0,
            dc_kw_nameplate=1.0,
        )


def test_result_round_trips_through_json() -> None:
    dc = _midday_curve(peak_dc_kw=8.0)
    result = apply_clipping(
        hourly_dc_kw=dc,
        inverter_ac_kw=5.0,
        dc_kw_nameplate=8.0,
    )
    payload = result.model_dump(mode="json")
    revived = ClippingResult.model_validate(payload)
    assert revived.clipping_loss_kwh == pytest.approx(result.clipping_loss_kwh)
    assert revived.clipped_hours == result.clipped_hours
    assert revived.is_aggressive_ratio == result.is_aggressive_ratio

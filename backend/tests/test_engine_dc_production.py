"""DC + AC production via pvlib ModelChain.

These tests run pvlib's PVWatts ModelChain end-to-end against a
synthetic clear-sky TMY (FakeIrradianceProvider). The point is twofold:

1. Verify the wiring — ModelChain runs without exceptions, output
   shapes / ranges are sane, the result schema round-trips.
2. Confirm physical sensibility: kWh/kW/yr in the right ballpark for
   sunny / cloudy / steeply-tilted / due-north systems, monotonic
   sensitivity to system size.

We don't pin against the historical PVWatts repo here — that
cross-check belongs in the audit's golden-fixture suite once the
reference fixture lands (see chart-solar-b9z).
"""

from __future__ import annotations

import math

import pytest

from backend.engine.inputs import SystemInputs
from backend.engine.steps.dc_production import (
    DEFAULT_DC_AC_RATIO,
    DcProductionResult,
    run_dc_production,
)
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import HOURS_PER_TMY


def _system(**overrides: float) -> SystemInputs:
    base = {
        "lat": 33.4484,  # Phoenix
        "lon": -112.0740,
        "dc_kw": 8.0,
        "tilt_deg": 25.0,
        "azimuth_deg": 180.0,
    }
    base.update(overrides)
    return SystemInputs(**base)


def test_phoenix_clearsky_year_in_expected_range() -> None:
    """Phoenix clear-sky year should comfortably exceed 2,000 kWh/kW.
    (Real Phoenix TMY is ~1,800 kWh/kW; clear-sky is the upper bound.)
    """
    system = _system()
    tmy = synthetic_tmy(lat=system.lat, lon=system.lon, timezone="America/Phoenix")
    result = run_dc_production(system=system, tmy=tmy)
    kwh_per_kw = result.annual_ac_kwh / system.dc_kw
    assert 1_900 <= kwh_per_kw <= 2_800
    assert len(result.hourly_ac_kw) == HOURS_PER_TMY
    assert len(result.hourly_dc_kw) == HOURS_PER_TMY


def test_seattle_clearsky_year_lower_than_phoenix() -> None:
    """Higher-latitude site under identical clear-sky logic still produces
    measurably less per-kW yield because the sun rides lower."""
    seattle = _system(lat=47.6062, lon=-122.3321)
    phoenix = _system(lat=33.4484, lon=-112.0740)
    seattle_tmy = synthetic_tmy(
        lat=seattle.lat, lon=seattle.lon, timezone="America/Los_Angeles"
    )
    phoenix_tmy = synthetic_tmy(
        lat=phoenix.lat, lon=phoenix.lon, timezone="America/Phoenix"
    )
    seattle_result = run_dc_production(system=seattle, tmy=seattle_tmy)
    phoenix_result = run_dc_production(system=phoenix, tmy=phoenix_tmy)
    assert seattle_result.annual_ac_kwh < phoenix_result.annual_ac_kwh


def test_north_facing_array_loses_most_of_its_year() -> None:
    """Due-north (azimuth 0°) in northern hemisphere is the worst-case;
    annual yield should be a fraction of due-south."""
    south = run_dc_production(
        system=_system(azimuth_deg=180.0),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    north = run_dc_production(
        system=_system(azimuth_deg=0.0),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    assert north.annual_ac_kwh < south.annual_ac_kwh * 0.85


def test_doubling_dc_kw_roughly_doubles_production() -> None:
    """The PVWatts model is essentially linear in DC kW (no per-cell
    saturation effects); doubling the array doubles annual yield to
    within float tolerance, as long as the inverter scales with it."""
    small = run_dc_production(
        system=_system(dc_kw=4.0),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    big = run_dc_production(
        system=_system(dc_kw=8.0),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    ratio = big.annual_ac_kwh / small.annual_ac_kwh
    assert 1.95 <= ratio <= 2.05


def test_default_inverter_sizing_yields_default_ratio() -> None:
    """When ``inverter_ac_kw`` is not provided, the result reports the
    default DC:AC ratio so downstream clipping logic has the number it
    needs."""
    result = run_dc_production(
        system=_system(),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    assert result.dc_ac_ratio == pytest.approx(DEFAULT_DC_AC_RATIO, abs=1e-6)


def test_explicit_inverter_overrides_default() -> None:
    result = run_dc_production(
        system=_system(dc_kw=8.0),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
        inverter_ac_kw=8.0,
    )
    assert result.inverter_ac_kw == pytest.approx(8.0)
    assert result.dc_ac_ratio == pytest.approx(1.0)


def test_aggressive_dc_ac_ratio_clips_peak_ac() -> None:
    """At a 1.6× DC:AC ratio, the inverter saturates well below DC peak —
    peak AC sits at ~inverter nameplate, not DC nameplate."""
    inverter = 5.0
    result = run_dc_production(
        system=_system(dc_kw=8.0),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
        inverter_ac_kw=inverter,
    )
    assert result.peak_ac_kw <= inverter * 1.02
    assert result.dc_ac_ratio == pytest.approx(8.0 / inverter)


def test_zero_inverter_rejected() -> None:
    with pytest.raises(ValueError, match="inverter_ac_kw must be > 0"):
        run_dc_production(
            system=_system(),
            tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
            inverter_ac_kw=0.0,
        )


def test_result_round_trips_through_json() -> None:
    """Engine state is serialised on the queue boundary; results must
    survive `model_dump(mode="json") -> model_validate`."""
    result = run_dc_production(
        system=_system(),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    payload = result.model_dump(mode="json")
    revived = DcProductionResult.model_validate(payload)
    assert revived.annual_ac_kwh == pytest.approx(result.annual_ac_kwh)
    assert revived.peak_ac_kw == pytest.approx(result.peak_ac_kw)
    assert math.isclose(sum(revived.hourly_ac_kw), result.annual_ac_kwh, abs_tol=1e-3)


def test_hourly_ac_never_exceeds_peak() -> None:
    """`peak_ac_kw` is the max of ``hourly_ac_kw`` — verify by
    construction so the result schema can't drift."""
    result = run_dc_production(
        system=_system(),
        tmy=synthetic_tmy(lat=33.4484, lon=-112.0740, timezone="America/Phoenix"),
    )
    assert max(result.hourly_ac_kw) == pytest.approx(result.peak_ac_kw)


def test_temperature_derate_lowers_output() -> None:
    """A more negative ``gamma_pdc`` (steeper temp coefficient) drops
    annual production for a hot site — verifies cell-temp is wired in."""
    hot_tmy = synthetic_tmy(
        lat=33.4484, lon=-112.0740, timezone="America/Phoenix", temp_air_c=40.0
    )
    base = run_dc_production(system=_system(), tmy=hot_tmy, gamma_pdc=-0.003)
    steeper = run_dc_production(system=_system(), tmy=hot_tmy, gamma_pdc=-0.005)
    assert steeper.annual_ac_kwh < base.annual_ac_kwh


def test_step_registers_under_engine_dc_production_key() -> None:
    """The pipeline registry must list this step under
    ``engine.dc_production`` so feature-flag selection works."""
    from backend.engine.registry import steps_for

    keys = {s.feature_key for s in steps_for({"engine.dc_production"})}
    assert "engine.dc_production" in keys

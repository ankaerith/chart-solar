"""Cell-temperature derating — pure-math + pvlib-backed.

Synthetic POA / temp / wind arrays so these run independent of the
dc_production step landing first.
"""

from __future__ import annotations

import pytest

from backend.engine.steps.temperature import (
    DEFAULT_GAMMA_PDC,
    SAPM_MOUNTS,
    T_REF_C,
    cell_temperature_celsius,
    derate_dc_for_temperature,
    temperature_derate_factor,
)


def test_cell_temp_at_stc_close_to_25c() -> None:
    """At low POA + ambient ≈25 °C + 1 m/s wind, cell temp should sit
    near ambient — the panel hasn't heated up yet."""
    cell_temp = cell_temperature_celsius(
        hourly_poa_w_m2=[100.0],
        hourly_temp_air_c=[25.0],
        hourly_wind_speed_m_s=[1.0],
    )
    assert 25.0 <= cell_temp[0] <= 31.0


def test_cell_temp_rises_with_irradiance() -> None:
    cool = cell_temperature_celsius(
        hourly_poa_w_m2=[200.0],
        hourly_temp_air_c=[25.0],
        hourly_wind_speed_m_s=[1.0],
    )
    hot = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[25.0],
        hourly_wind_speed_m_s=[1.0],
    )
    assert hot[0] > cool[0]


def test_cell_temp_drops_with_wind() -> None:
    """Higher wind → more convective cooling → lower cell temp."""
    calm = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[35.0],
        hourly_wind_speed_m_s=[0.5],
    )
    breezy = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[35.0],
        hourly_wind_speed_m_s=[5.0],
    )
    assert breezy[0] < calm[0]


def test_close_mount_runs_hotter_than_open_rack() -> None:
    """Close-mount roof installs lose convection — a known audit flag
    for hot climates."""
    open_rack = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[35.0],
        hourly_wind_speed_m_s=[1.0],
        sapm_mount="open_rack_glass_glass",
    )
    close_mount = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[35.0],
        hourly_wind_speed_m_s=[1.0],
        sapm_mount="close_mount_glass_glass",
    )
    assert close_mount[0] > open_rack[0]


def test_faiman_model_within_a_few_degrees_of_sapm() -> None:
    """SAPM and Faiman should agree closely on residential conditions."""
    sapm = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[25.0],
        hourly_wind_speed_m_s=[1.0],
        model="sapm",
    )
    faiman = cell_temperature_celsius(
        hourly_poa_w_m2=[1000.0],
        hourly_temp_air_c=[25.0],
        hourly_wind_speed_m_s=[1.0],
        model="faiman",
    )
    assert abs(sapm[0] - faiman[0]) < 5.0


def test_derate_factor_one_at_reference_temp() -> None:
    factors = temperature_derate_factor(hourly_cell_temp_c=[T_REF_C])
    assert factors[0] == pytest.approx(1.0)


def test_derate_factor_below_one_at_hot_panel() -> None:
    """65 °C cell, -0.004 gamma → 1 + (-0.004)(40) = 0.84."""
    factors = temperature_derate_factor(hourly_cell_temp_c=[65.0], gamma_pdc=-0.004)
    assert factors[0] == pytest.approx(0.84, abs=1e-12)


def test_derate_factor_above_one_at_cold_panel() -> None:
    """At a cold panel (10 °C), the negative gamma actually *boosts*
    output above nameplate. Solar in Anchorage in January benefits."""
    factors = temperature_derate_factor(hourly_cell_temp_c=[10.0], gamma_pdc=-0.004)
    assert factors[0] > 1.0


def test_derate_factor_clamps_at_zero() -> None:
    """Pathological cell temp + gamma combo would push the linear
    model below zero — we clamp."""
    factors = temperature_derate_factor(hourly_cell_temp_c=[1000.0], gamma_pdc=-0.005, t_ref_c=25.0)
    assert factors[0] == 0.0


def test_derate_dc_full_pipeline() -> None:
    """End-to-end: a hot Phoenix afternoon hour drops AC ~12-16 %."""
    dc_kw = [8.0]
    poa = [1000.0]
    temp_air = [40.0]
    wind = [1.0]
    derated, series = derate_dc_for_temperature(
        hourly_dc_kw=dc_kw,
        hourly_poa_w_m2=poa,
        hourly_temp_air_c=temp_air,
        hourly_wind_speed_m_s=wind,
    )
    assert series.peak_cell_temp_c > 50.0
    assert series.peak_cell_temp_c < 80.0
    assert 0.80 < derated[0] / dc_kw[0] < 0.92


def test_derate_dc_returns_unchanged_at_reference() -> None:
    """When cell temp is exactly the reference, output is unchanged.
    Construct a synthetic case with no irradiance + 25 °C ambient."""
    dc_kw = [0.0, 0.0]
    derated, series = derate_dc_for_temperature(
        hourly_dc_kw=dc_kw,
        hourly_poa_w_m2=[0.0, 0.0],
        hourly_temp_air_c=[25.0, 25.0],
        hourly_wind_speed_m_s=[1.0, 1.0],
    )
    assert series.peak_cell_temp_c == pytest.approx(25.0, abs=0.01)
    for f in series.hourly_derate_factor:
        assert f == pytest.approx(1.0, abs=1e-3)
    assert derated == [0.0, 0.0]


def test_default_gamma_matches_pvwatts() -> None:
    assert DEFAULT_GAMMA_PDC == pytest.approx(-0.004)


def test_known_sapm_mounts_present() -> None:
    """The audit relies on these mount keys being available — pin them."""
    assert "open_rack_glass_glass" in SAPM_MOUNTS
    assert "close_mount_glass_glass" in SAPM_MOUNTS


def test_unknown_mount_rejected() -> None:
    with pytest.raises(ValueError, match="unknown sapm_mount"):
        cell_temperature_celsius(
            hourly_poa_w_m2=[1000.0],
            hourly_temp_air_c=[25.0],
            hourly_wind_speed_m_s=[1.0],
            sapm_mount="floating_in_space",
        )


def test_misaligned_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="must align"):
        cell_temperature_celsius(
            hourly_poa_w_m2=[1000.0, 900.0],
            hourly_temp_air_c=[25.0],
            hourly_wind_speed_m_s=[1.0],
        )


def test_empty_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        cell_temperature_celsius(
            hourly_poa_w_m2=[],
            hourly_temp_air_c=[],
            hourly_wind_speed_m_s=[],
        )


def test_dc_poa_misalignment_rejected() -> None:
    with pytest.raises(ValueError, match="must align"):
        derate_dc_for_temperature(
            hourly_dc_kw=[1.0, 2.0],
            hourly_poa_w_m2=[1000.0],
            hourly_temp_air_c=[25.0],
            hourly_wind_speed_m_s=[1.0],
        )

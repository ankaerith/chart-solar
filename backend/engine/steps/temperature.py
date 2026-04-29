"""Cell-temperature derating.

Modules run hot — a panel sitting in 35 °C Texas afternoon sun can hit
65 °C cell temperature, and at a typical -0.4 %/°C power coefficient
that's a 16 % derate vs. the lab-bench (25 °C) nameplate. Audits in
TX / AZ / Phoenix routinely flip on the "thermal derate" flag because
of this.

This step exposes pvlib's SAPM and Faiman cell-temperature models as
pure Python functions over hourly arrays, plus the multiplicative
temperature derate factor those drive. Composes on top of the
``engine.dc_production`` step's hourly DC output — pvlib already does
this internally inside ModelChain, so the typical call here is for
"replay this audit with a different mount type" what-ifs.

The SAPM ``open_rack_glass_glass`` parameters are the pvlib default
for unframed bifacial; ``close_mount_glass_glass`` is a typical roof
mount (panels close to the surface, less convection).
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pvlib
from pydantic import BaseModel, Field

CellTemperatureModel = Literal["sapm", "faiman"]

#: Reference cell temperature for the temperature coefficient — STC.
T_REF_C: float = 25.0

#: PVWatts default. Manufacturer data sheets vary by chemistry; mono-Si
#: is closer to ``-0.0035``, thin-film closer to ``-0.0025``.
DEFAULT_GAMMA_PDC: float = -0.004

#: Convenience: the SAPM mount presets pvlib ships, exposed here so
#: callers don't have to reach into pvlib namespace.
SAPM_MOUNTS: dict[str, dict[str, float]] = {
    name: {**params}
    for name, params in pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"].items()
}


class CellTemperatureSeries(BaseModel):
    """Per-hour cell temperatures + the derate factors they imply."""

    hourly_cell_temp_c: list[float] = Field(..., min_length=1)
    hourly_derate_factor: list[float] = Field(..., min_length=1)
    model: CellTemperatureModel
    gamma_pdc: float
    peak_cell_temp_c: float
    annual_avg_derate: float


def cell_temperature_celsius(
    *,
    hourly_poa_w_m2: list[float],
    hourly_temp_air_c: list[float],
    hourly_wind_speed_m_s: list[float],
    model: CellTemperatureModel = "sapm",
    sapm_mount: str = "open_rack_glass_glass",
    faiman_u0: float = 25.0,
    faiman_u1: float = 6.84,
) -> list[float]:
    """Hourly cell temperature from POA + ambient + wind.

    SAPM uses pvlib's exponential mount-dependent fit (King et al.
    2004); Faiman is the simpler linear model favored by IEC 61853
    and used in PVGIS. Both produce comparable numbers at residential
    scale (<1 °C divergence on hourly average).
    """
    n = len(hourly_poa_w_m2)
    if not (len(hourly_temp_air_c) == len(hourly_wind_speed_m_s) == n):
        raise ValueError("input arrays must align in length")
    if n == 0:
        raise ValueError("input arrays must be non-empty")

    poa = np.asarray(hourly_poa_w_m2, dtype=float)
    air = np.asarray(hourly_temp_air_c, dtype=float)
    wind = np.asarray(hourly_wind_speed_m_s, dtype=float)

    if model == "sapm":
        if sapm_mount not in SAPM_MOUNTS:
            raise ValueError(
                f"unknown sapm_mount {sapm_mount!r}; known: {sorted(SAPM_MOUNTS)}"
            )
        params = SAPM_MOUNTS[sapm_mount]
        result = pvlib.temperature.sapm_cell(
            poa_global=poa,
            temp_air=air,
            wind_speed=wind,
            a=params["a"],
            b=params["b"],
            deltaT=params["deltaT"],
        )
    elif model == "faiman":
        result = pvlib.temperature.faiman(
            poa_global=poa,
            temp_air=air,
            wind_speed=wind,
            u0=faiman_u0,
            u1=faiman_u1,
        )
    else:
        raise ValueError(f"unknown cell-temperature model: {model!r}")

    return [float(v) for v in np.asarray(result, dtype=float).tolist()]


def temperature_derate_factor(
    *,
    hourly_cell_temp_c: list[float],
    gamma_pdc: float = DEFAULT_GAMMA_PDC,
    t_ref_c: float = T_REF_C,
) -> list[float]:
    """Per-hour multiplicative derate from cell temperature.

    factor = 1 + gamma_pdc * (T_cell - T_ref)

    For panels above 25 °C with a negative gamma, the factor is <1
    (output drops). At gamma=-0.004 and T_cell=65 °C the factor is
    1 + (-0.004)(40) = 0.84 — a 16 % output hit on a hot afternoon.

    Negative factors are clamped at zero — at extreme temperatures
    the linear model can theoretically drive output below zero, which
    isn't physical. A more realistic non-linear model is deferred.
    """
    return [max(0.0, 1.0 + gamma_pdc * (t_cell - t_ref_c)) for t_cell in hourly_cell_temp_c]


def derate_dc_for_temperature(
    *,
    hourly_dc_kw: list[float],
    hourly_poa_w_m2: list[float],
    hourly_temp_air_c: list[float],
    hourly_wind_speed_m_s: list[float],
    gamma_pdc: float = DEFAULT_GAMMA_PDC,
    model: CellTemperatureModel = "sapm",
    sapm_mount: str = "open_rack_glass_glass",
) -> tuple[list[float], CellTemperatureSeries]:
    """Apply temperature derate to an hourly DC array.

    Returns the derated DC array + the diagnostic series so the audit
    can surface peak cell temperature + annual-average derate as a
    flag. The diagnostic series is what the tornado plot reads to sweep
    mount types ("would close-mount add 2 °C to your peaks?").
    """
    if len(hourly_dc_kw) != len(hourly_poa_w_m2):
        raise ValueError("hourly_dc_kw and hourly_poa_w_m2 must align")

    cell_temp = cell_temperature_celsius(
        hourly_poa_w_m2=hourly_poa_w_m2,
        hourly_temp_air_c=hourly_temp_air_c,
        hourly_wind_speed_m_s=hourly_wind_speed_m_s,
        model=model,
        sapm_mount=sapm_mount,
    )
    factors = temperature_derate_factor(hourly_cell_temp_c=cell_temp, gamma_pdc=gamma_pdc)
    derated_dc = [dc * f for dc, f in zip(hourly_dc_kw, factors, strict=True)]

    avg_derate = sum(factors) / len(factors)
    series = CellTemperatureSeries(
        hourly_cell_temp_c=cell_temp,
        hourly_derate_factor=factors,
        model=model,
        gamma_pdc=gamma_pdc,
        peak_cell_temp_c=max(cell_temp),
        annual_avg_derate=avg_derate,
    )
    return derated_dc, series

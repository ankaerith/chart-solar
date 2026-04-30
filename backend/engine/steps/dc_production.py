"""DC + AC production via pvlib's ModelChain.

The PVWatts modelchain (`ModelChain.with_pvwatts`) is the right level
of abstraction for kW-DC-nameplate inputs: the user gave us tilt /
azimuth / DC kW, not module-spec sheets. SAPM-grade physics is
deferred until extraction surfaces a module model number; this step
hits the 5-8 % accuracy band that satisfies the audit's headline
forecast.

Cell-temperature derating (SAPM `open_rack_glass_glass`) and inverter
clipping (saturation at ``inverter_ac_kw``) are both applied by pvlib
inside ``ModelChain.with_pvwatts`` — see ADR 0006 for why we don't
have separate engine steps for either. ``gamma_pdc`` and
``temperature_model`` are extension points for the extraction
pipeline (real spec sheets), not user-facing toggles.
"""

from __future__ import annotations

import pandas as pd
import pvlib
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.pvsystem import Array, FixedMount, PVSystem
from pydantic import BaseModel, Field

from backend.engine.inputs import SystemInputs
from backend.engine.registry import register
from backend.providers.irradiance import HOURS_PER_TMY, TmyData, tmy_datetime_index

#: PVWatts default temperature coefficient of power (1/°C). Manufacturer
#: data sheets vary by chemistry — mono-Si is closer to ``-0.0035``,
#: thin-film closer to ``-0.0025`` — but ``-0.004`` is the value pvlib
#: ships as the PVWatts canonical and the figure used in nearly every
#: published US residential study.
DEFAULT_GAMMA_PDC: float = -0.004

#: Default DC:AC ratio when the user hasn't extracted a real inverter
#: nameplate. The audit will flag overly aggressive ratios separately;
#: 1.20 reflects current US installer practice (oversized DC strings
#: on smaller inverters to extract more shoulder-hour energy).
DEFAULT_DC_AC_RATIO: float = 1.20


class DcProductionResult(BaseModel):
    """Hourly + annual production from one ModelChain run.

    The hourly arrays are exactly ``HOURS_PER_TMY`` long so they align
    one-to-one with the TmyData inputs. ``hourly_dc_kw`` is the array's
    total DC output before inverter clipping; ``hourly_ac_kw`` is the
    inverter's clipped AC output. Both are in kilowatts (not watts) so
    downstream finance / tariff steps don't have to remember.
    """

    hourly_dc_kw: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    hourly_ac_kw: list[float] = Field(..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    annual_dc_kwh: float = Field(..., ge=0.0)
    annual_ac_kwh: float = Field(..., ge=0.0)
    peak_ac_kw: float = Field(..., ge=0.0)
    inverter_ac_kw: float = Field(..., gt=0.0)
    dc_ac_ratio: float = Field(..., gt=0.0)


def _weather_frame(tmy: TmyData, index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ghi": tmy.ghi_w_m2,
            "dni": tmy.dni_w_m2,
            "dhi": tmy.dhi_w_m2,
            "temp_air": tmy.temp_air_c,
            "wind_speed": tmy.wind_speed_m_s,
        },
        index=index,
    )


@register("engine.dc_production")
def run_dc_production(
    *,
    system: SystemInputs,
    tmy: TmyData,
    inverter_ac_kw: float | None = None,
    gamma_pdc: float = DEFAULT_GAMMA_PDC,
    temperature_model: str = "open_rack_glass_glass",
) -> DcProductionResult:
    """Run pvlib's PVWatts ModelChain for one location-year.

    Inputs are deliberately minimal: tilt / azimuth / DC kW from
    extraction (or a sane default), TMY hourly weather from the
    irradiance providers. The inverter is sized off
    ``DEFAULT_DC_AC_RATIO`` when not supplied; the audit's "aggressive
    DC:AC ratio" flag reads ``DcProductionResult.dc_ac_ratio``.
    """
    if inverter_ac_kw is None:
        inverter_ac_kw = system.dc_kw / DEFAULT_DC_AC_RATIO
    if inverter_ac_kw <= 0:
        raise ValueError("inverter_ac_kw must be > 0")

    index = tmy_datetime_index(tmy.timezone)
    weather = _weather_frame(tmy, index)

    location = Location(
        latitude=system.lat,
        longitude=system.lon,
        tz=tmy.timezone,
        altitude=tmy.elevation_m,
    )

    temp_params = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][temperature_model]
    array = Array(
        mount=FixedMount(
            surface_tilt=system.tilt_deg,
            surface_azimuth=system.azimuth_deg,
        ),
        module_parameters={"pdc0": system.dc_kw * 1000.0, "gamma_pdc": gamma_pdc},
        temperature_model_parameters=temp_params,
    )
    pv_system = PVSystem(
        arrays=[array],
        inverter_parameters={"pdc0": inverter_ac_kw * 1000.0},
    )
    mc = ModelChain.with_pvwatts(pv_system, location)
    mc.run_model(weather)

    dc_kw = (_aligned_w_series(mc.results.dc, index) / 1000.0).clip(lower=0.0)
    ac_kw = (_aligned_w_series(mc.results.ac, index) / 1000.0).clip(lower=0.0)

    return DcProductionResult(
        hourly_dc_kw=dc_kw.tolist(),
        hourly_ac_kw=ac_kw.tolist(),
        annual_dc_kwh=float(dc_kw.sum()),
        annual_ac_kwh=float(ac_kw.sum()),
        peak_ac_kw=float(ac_kw.max()),
        inverter_ac_kw=inverter_ac_kw,
        dc_ac_ratio=system.dc_kw / inverter_ac_kw,
    )


def _aligned_w_series(value: object, index: pd.DatetimeIndex) -> pd.Series:
    """PVWatts ModelChain returns a Series for both `.dc` and `.ac`;
    reindex defensively so a future pvlib upgrade that drops a row
    fills with 0 rather than NaN."""
    if not isinstance(value, pd.Series):
        raise TypeError(f"unexpected ModelChain result type: {type(value).__name__}")
    return value.reindex(index).fillna(0.0).astype(float)

"""Snow loss via pvlib's Townsend monthly model.

``pvlib.snow.loss_townsend`` operates on monthly aggregates: total
snowfall (cm), event count, mean POA insolation (Wh/m²), mean air
temperature (°C), mean relative humidity (%), array tilt, and two
geometry parameters (slant height, lower-edge height). It returns a
12-element vector of monthly DC capacity loss fractions.

We layer that monthly loss onto the hourly AC production stream by
calling ``apply_monthly_factors`` with ``(1 − loss[m])`` per month —
``engine.snow``'s ``adjusted_hourly_ac_kw`` is therefore the post-snow
AC stream the downstream tariff / battery / finance steps consume.

The step no-ops (returns ``None``, which the pipeline adapter treats
as "skip") when the prerequisite TMY columns are absent —
``snowfall_cm_per_month`` or ``relative_humidity_pct_per_month``. PVGIS
sites without the ERA5-Land sibling lookup hit that path; their
forecasts pass through with no snow derate, which is a defensible
floor (zero-snow assumption) until the data layer is universal.
"""

from __future__ import annotations

import numpy as np
import pvlib.snow
from pydantic import BaseModel, Field

from backend.domain.calendar import (
    aggregate_hourly_to_monthly_mean,
    aggregate_hourly_to_monthly_sum,
    apply_monthly_factors,
)
from backend.domain.tmy import HOURS_PER_TMY, TmyData
from backend.engine.inputs import SystemInputs
from backend.engine.registry import register
from backend.engine.steps.dc_production import DcProductionResult

#: Average centimetres of snow per "snow event" — Townsend's model
#: counts events as days with >1 inch (≈2.54 cm) of snowfall. We don't
#: have daily granularity (only monthly aggregates), so we approximate
#: events as ``snow_total_cm / DEFAULT_CM_PER_EVENT``. 5 cm is the
#: midpoint of typical event sizes for snow-belt US/Canadian sites:
#: small enough that low-snow months still register an event, large
#: enough that a 100 cm month doesn't claim 100 events.
DEFAULT_CM_PER_EVENT: float = 5.0

#: Slant height (m) of one row of modules. 1.7 m is one tier of
#: 60-cell residential modules in portrait. Townsend's model uses this
#: to compute the area available for snow to slide off; rooftop and
#: ground-mount residential installs cluster around this value.
DEFAULT_SLANT_HEIGHT_M: float = 1.7

#: Distance (m) from the array's lower edge to the surface the snow
#: piles against. For pitched-roof residential installs the eave is
#: usually 2 m+ above ground (snow can't pile up to the array), so
#: 2.0 m is a sane default — Townsend's model is most sensitive to
#: this on ground mounts where the value is closer to 0.3-0.5 m.
DEFAULT_LOWER_EDGE_HEIGHT_M: float = 2.0


class SnowLossResult(BaseModel):
    """Monthly snow loss + the post-snow hourly AC stream.

    ``monthly_loss_fraction[m]`` is the DC capacity loss the Townsend
    model attributes to month ``m + 1`` (0.0 = no loss, 1.0 = total
    blockage). ``adjusted_hourly_ac_kw`` is the AC production stream
    after applying ``(1 − loss[m])`` per hour-in-month;
    ``adjusted_annual_ac_kwh`` is its sum.
    """

    monthly_loss_fraction: list[float] = Field(..., min_length=12, max_length=12)
    adjusted_hourly_ac_kw: list[float] = Field(
        ..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY
    )
    adjusted_annual_ac_kwh: float = Field(..., ge=0.0)


@register("engine.snow")
def run_snow_loss(
    *,
    tmy: TmyData,
    system: SystemInputs,
    dc: DcProductionResult,
    cm_per_event: float = DEFAULT_CM_PER_EVENT,
    slant_height_m: float | None = None,
    lower_edge_height_m: float | None = None,
    string_factor: float | None = None,
) -> SnowLossResult | None:
    """Run pvlib's Townsend monthly snow-loss model against the TMY.

    Returns ``None`` (skip) when the TMY lacks monthly snowfall or
    relative humidity — both are required Townsend inputs. The pipeline
    adapter treats ``None`` as "no snow derate this run" and leaves the
    pre-snow ``engine.dc_production`` stream as the source of truth.

    Per-install array geometry resolves in order: explicit kwarg wins,
    otherwise ``system.snow_geometry`` (when installer-quote extraction
    surfaces it), otherwise residential-rooftop defaults.
    """
    if tmy.snowfall_cm_per_month is None:
        return None
    if tmy.relative_humidity_pct_per_month is None:
        return None

    geom = system.snow_geometry

    def _resolve(override: float | None, attr: str, default: float) -> float:
        if override is not None:
            return override
        if geom is not None:
            return float(getattr(geom, attr))
        return default

    resolved_slant = _resolve(slant_height_m, "slant_height_m", DEFAULT_SLANT_HEIGHT_M)
    resolved_lower_edge = _resolve(
        lower_edge_height_m, "lower_edge_height_m", DEFAULT_LOWER_EDGE_HEIGHT_M
    )
    resolved_string = _resolve(string_factor, "string_factor", 1.0)

    monthly_temp_c = aggregate_hourly_to_monthly_mean(tmy.temp_air_c)
    # Townsend's `poa_global` is monthly insolation (Wh/m²), an energy
    # total — not mean irradiance power. Each hourly value is W/m² over
    # one hour, so the monthly sum is the right Wh/m² aggregate.
    monthly_poa_wh_m2 = aggregate_hourly_to_monthly_sum(dc.hourly_poa_w_m2)

    snow_total = np.asarray(tmy.snowfall_cm_per_month, dtype=float)
    snow_events = snow_total / cm_per_event if cm_per_event > 0 else np.zeros_like(snow_total)

    loss = pvlib.snow.loss_townsend(
        snow_total=snow_total,
        snow_events=snow_events,
        surface_tilt=system.tilt_deg,
        relative_humidity=np.asarray(tmy.relative_humidity_pct_per_month, dtype=float),
        temp_air=np.asarray(monthly_temp_c, dtype=float),
        poa_global=np.asarray(monthly_poa_wh_m2, dtype=float),
        slant_height=resolved_slant,
        lower_edge_height=resolved_lower_edge,
        string_factor=resolved_string,
    )

    monthly_loss = [max(0.0, min(1.0, float(value))) for value in loss]
    monthly_factors = [1.0 - loss_m for loss_m in monthly_loss]
    adjusted_hourly = apply_monthly_factors(
        hourly=dc.hourly_ac_kw,
        monthly_factors=monthly_factors,
    )

    return SnowLossResult(
        monthly_loss_fraction=monthly_loss,
        adjusted_hourly_ac_kw=adjusted_hourly,
        adjusted_annual_ac_kwh=sum(adjusted_hourly),
    )


__all__ = [
    "DEFAULT_CM_PER_EVENT",
    "DEFAULT_LOWER_EDGE_HEIGHT_M",
    "DEFAULT_SLANT_HEIGHT_M",
    "SnowLossResult",
    "run_snow_loss",
]

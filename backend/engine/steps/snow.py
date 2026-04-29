"""Snow loss model (latitude + tilt dependent).

Snow on panels blocks production until either insolation melts it,
gravity sheds it (steep-tilt arrays self-clear faster), or someone
clears it manually. Annual loss ranges from negligible at sub-35°
latitudes (Phoenix, Atlanta) to 5-10 % around 45° (Boulder, Erie) to
10-20 % above 55° (Anchorage, Stockholm).

This step uses a published-empirical lat-band table for the
*monthly* loss distribution, then applies a tilt-shedding adjustment
(steeper tilts lose less because snow slides off). The output is 12
monthly factors that compose with the soiling step's curve — both are
multiplicative, both project onto the hourly stream by month-of-year
membership.

A pvlib.snow.loss_townsend-backed path is the right upgrade once
we route monthly snowfall + RH from the irradiance providers; until
then the lat-band defaults give a within-2 % envelope on the audit's
headline number for sites with non-trivial snow.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

#: Below this latitude, snow loss is treated as zero (default: ATL,
#: Phoenix, Houston don't see panel-blocking snow). Caller can pass
#: ``snow_threshold_lat`` to override.
DEFAULT_SNOW_THRESHOLD_LAT: float = 35.0

#: Above this tilt, snow sheds quickly under its own weight; below it,
#: snow accumulates. Empirically supported by Marion et al. 2013.
NATURAL_SHED_TILT_DEG: float = 40.0

#: 12-month *loss* fractions (Jan..Dec) — these are subtracted from 1
#: to produce derate factors. Bands are coarse climate envelopes:
#:
#: * lat 35-45°: temperate-winter (Boulder, Pittsburgh, Boston)
#: * lat 45-55°: cold-winter (Minneapolis, Calgary, southern Sweden)
#: * lat >55°:   subarctic (Anchorage, Stockholm, Helsinki)
LAT_BAND_LOSS_FRACTIONS: dict[str, tuple[float, ...]] = {
    "temperate-winter": (
        0.08, 0.05, 0.02, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.02, 0.06,
    ),
    "cold-winter": (
        0.20, 0.15, 0.08, 0.02, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.02, 0.10, 0.18,
    ),
    "subarctic": (
        0.40, 0.30, 0.20, 0.10, 0.02, 0.0,
        0.0, 0.0, 0.02, 0.10, 0.25, 0.38,
    ),
}


class SnowLossCurve(BaseModel):
    """12 monthly *loss* fractions (Jan..Dec) and the derived factors."""

    lat: float
    tilt_deg: float
    band: str
    monthly_factors: list[float] = Field(..., min_length=12, max_length=12)
    annual_avg_factor: float = Field(..., ge=0.0, le=1.0)


def _lat_band(lat: float) -> str | None:
    abs_lat = abs(lat)
    if abs_lat < DEFAULT_SNOW_THRESHOLD_LAT:
        return None
    if abs_lat < 45.0:
        return "temperate-winter"
    if abs_lat < 55.0:
        return "cold-winter"
    return "subarctic"


def _tilt_shed_factor(tilt_deg: float) -> float:
    """Multiplicative reduction in snow loss from a steep array.

    At tilts ≥ ``NATURAL_SHED_TILT_DEG`` (40°), snow sheds within
    hours; we model this as 50 % loss reduction. Between 25° and 40°
    we linearly interpolate, and below 25° we apply no reduction.
    The numbers are Marion et al. 2013-shaped — pinning to ±5 % is
    reasonable.
    """
    if tilt_deg >= NATURAL_SHED_TILT_DEG:
        return 0.5
    if tilt_deg <= 25.0:
        return 1.0
    fraction = (tilt_deg - 25.0) / (NATURAL_SHED_TILT_DEG - 25.0)
    return 1.0 - fraction * 0.5


def snow_loss_curve(
    *,
    lat: float,
    tilt_deg: float,
    snow_threshold_lat: float = DEFAULT_SNOW_THRESHOLD_LAT,
) -> SnowLossCurve:
    """Build a 12-month snow-loss curve for a given lat + tilt.

    Returns all-1.0 factors for sub-threshold latitudes (no snow loss).
    For higher latitudes, picks the published-empirical lat-band loss
    table, then applies the tilt-shedding adjustment.
    """
    if not -90.0 <= lat <= 90.0:
        raise ValueError("lat must be in [-90, 90]")
    if not 0.0 <= tilt_deg <= 90.0:
        raise ValueError("tilt_deg must be in [0, 90]")

    if abs(lat) < snow_threshold_lat:
        # No snow loss south of the threshold.
        factors = [1.0] * 12
        return SnowLossCurve(
            lat=lat,
            tilt_deg=tilt_deg,
            band="no-snow",
            monthly_factors=factors,
            annual_avg_factor=1.0,
        )

    band = _lat_band(lat)
    assert band is not None  # _lat_band only returns None below threshold
    base_losses = LAT_BAND_LOSS_FRACTIONS[band]
    shed = _tilt_shed_factor(tilt_deg)
    adjusted_losses = [loss * shed for loss in base_losses]
    factors = [1.0 - loss for loss in adjusted_losses]
    avg = sum(factors) / 12.0
    return SnowLossCurve(
        lat=lat,
        tilt_deg=tilt_deg,
        band=band,
        monthly_factors=factors,
        annual_avg_factor=avg,
    )


def apply_monthly_snow_loss(
    *,
    hourly_kwh: list[float],
    curve: SnowLossCurve,
    hours_per_month: tuple[int, ...] = (
        744, 672, 744, 720, 744, 720,
        744, 744, 720, 744, 720, 744,
    ),
) -> list[float]:
    """Project the 12-month snow curve onto an hourly array.

    Mirrors ``apply_monthly_soiling`` so the two compose cleanly: a
    pipeline can chain ``hourly_kwh -> soiling -> snow`` and the
    result is just the product of the two derate factors per hour.
    """
    if sum(hours_per_month) != len(hourly_kwh):
        raise ValueError(
            f"hours_per_month sum ({sum(hours_per_month)}) must match "
            f"hourly_kwh length ({len(hourly_kwh)})"
        )
    if len(hours_per_month) != 12:
        raise ValueError("hours_per_month must have exactly 12 entries")

    out: list[float] = []
    cursor = 0
    for month_index, hours in enumerate(hours_per_month):
        factor = curve.monthly_factors[month_index]
        for _ in range(hours):
            out.append(hourly_kwh[cursor] * factor)
            cursor += 1
    return out

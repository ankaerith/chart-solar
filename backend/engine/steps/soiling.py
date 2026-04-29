"""Monthly soiling loss curve.

Solar panels accumulate dust, pollen, bird droppings, and ash between
rainfall / cleaning events. The loss is small per day but adds up:
1-3 % annual derate is typical for residential rooftops, 5-8 % in arid
or wildfire-prone regions (CA Central Valley, Phoenix outskirts,
Australian outback). NREL's published soiling-rate studies
(Mejia & Kleissl 2013; Ilse et al. 2019) drive the lat/climate
defaults here.

Output is 12 monthly factors (Jan..Dec) — each is the multiplicative
derate to apply across that month's hourly production. The pipeline
projects the monthly factors onto the hourly stream by month-of-year
membership; soiling itself is too low-frequency to model hourly.

Climate-band defaults are deliberately coarse — a site-specific
override is the upgrade path once we have curated regional soiling
data tables. See chart-solar-dws for the curated data layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ClimateBand = Literal["temperate", "arid", "tropical"]

#: 12-month derate factors (Jan..Dec) for a typical *temperate* climate
#: with regular rainfall. Derived from NREL field-study median.
TEMPERATE_FACTORS: tuple[float, ...] = (
    0.99,
    0.985,
    0.985,
    0.99,
    0.99,
    0.985,
    0.98,
    0.975,
    0.98,
    0.985,
    0.99,
    0.99,
)

#: Arid climate (CA Central Valley, Phoenix, Las Vegas). Long dry
#: summers compound dust → 5-8 % loss in shoulder months, partial
#: recovery in winter rains. Empirical envelope from Mejia & Kleissl.
ARID_FACTORS: tuple[float, ...] = (
    0.98,
    0.97,
    0.96,
    0.95,
    0.93,
    0.92,
    0.91,
    0.92,
    0.93,
    0.95,
    0.97,
    0.98,
)

#: Tropical climate — frequent rain washes panels naturally; pollen +
#: organic film are the dominant losses but recovery is fast.
TROPICAL_FACTORS: tuple[float, ...] = (
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
    0.99,
)

CLIMATE_BAND_FACTORS: dict[ClimateBand, tuple[float, ...]] = {
    "temperate": TEMPERATE_FACTORS,
    "arid": ARID_FACTORS,
    "tropical": TROPICAL_FACTORS,
}


class SoilingCurve(BaseModel):
    """12 monthly derate factors + a climate-band tag for traceability."""

    climate_band: ClimateBand
    monthly_factors: list[float] = Field(..., min_length=12, max_length=12)
    annual_avg_factor: float = Field(..., gt=0.0, le=1.0)


def soiling_curve(
    *,
    climate_band: ClimateBand = "temperate",
    monthly_factors: list[float] | None = None,
) -> SoilingCurve:
    """Build a 12-month soiling curve.

    Pass ``monthly_factors`` for a site-specific override; otherwise
    falls back to the climate-band defaults. Caller-supplied factors
    are validated to be in (0, 1] and exactly 12 long.
    """
    if monthly_factors is None:
        factors = list(CLIMATE_BAND_FACTORS[climate_band])
    else:
        if len(monthly_factors) != 12:
            raise ValueError(
                f"monthly_factors must have exactly 12 entries (got {len(monthly_factors)})"
            )
        for f in monthly_factors:
            if not 0.0 < f <= 1.0:
                raise ValueError(f"each factor must be in (0, 1]; got {f}")
        factors = list(monthly_factors)
    avg = sum(factors) / len(factors)
    return SoilingCurve(
        climate_band=climate_band,
        monthly_factors=factors,
        annual_avg_factor=avg,
    )


def climate_band_for_latitude(lat: float, *, dry_climate: bool = False) -> ClimateBand:
    """Coarse default routing by latitude band.

    The ``dry_climate`` override is the right upgrade hook once we
    integrate Köppen-Geiger climate classification — until then,
    callers in obvious arid zones (Phoenix, Las Vegas) pass the flag
    explicitly and bypass the latitude rule.
    """
    if dry_climate:
        return "arid"
    if -23.5 <= lat <= 23.5:
        return "tropical"
    return "temperate"


def apply_monthly_soiling(
    *,
    hourly_kwh: list[float],
    curve: SoilingCurve,
    hours_per_month: tuple[int, ...] = (
        744,
        672,
        744,
        720,
        744,
        720,
        744,
        744,
        720,
        744,
        720,
        744,
    ),
) -> list[float]:
    """Project the 12-month curve onto an hourly array.

    The default ``hours_per_month`` matches a non-leap year (8760
    total). Caller can override for leap years or partial-year
    inputs; the only constraint is ``sum(hours_per_month) ==
    len(hourly_kwh)`` so the projection is exact.
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

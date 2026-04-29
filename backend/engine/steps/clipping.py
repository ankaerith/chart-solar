"""DC:AC inverter clipping.

A pure-math modifier that converts an hourly DC array into an hourly
AC array, capping at the inverter's AC nameplate. The clipped energy
is the kWh "left on the table" by an undersized inverter — at high
DC:AC ratios this is *intentional* (shoulder-hour gains outweigh
midday losses), but the audit flags ratios above ~1.3 because they
also tend to correlate with installer overselling.

The step is composable: pvlib's ``ModelChain`` already does inverter
saturation when it computes AC from DC, but real audits often need
to *replay* clipping with a different inverter assumption (extracted
spec sheets, post-extraction what-ifs). This module is the pure
function that does that.

Inverter efficiency is folded in as a single nominal η; pvlib uses
the same ``eta_inv_nom`` shortcut in PVWatts mode. A more accurate
load-curve η model is deferred — the constant-η approximation is
≤1 % off the realistic curve at residential scale.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

#: Below ~96 % nominal a residential string inverter is end-of-life;
#: typical SolarEdge / Enphase / Tesla nameplates land at 96-98 %.
DEFAULT_INVERTER_EFFICIENCY: float = 0.97

#: Empirical threshold above which the audit raises the
#: "high DC:AC ratio" flag. Industry installer practice has crept
#: from 1.15 → 1.30 as inverter clipping became cheaper than
#: oversizing the AC side; values past this point are usually a
#: sign of installer kW-stacking rather than a deliberate
#: shoulder-hour optimisation.
AGGRESSIVE_RATIO_THRESHOLD: float = 1.30


class ClippingResult(BaseModel):
    """Clipped AC stream + the loss accounting to surface in the audit."""

    hourly_ac_kw: list[float] = Field(..., min_length=1)
    inverter_ac_kw: float = Field(..., gt=0.0)
    inverter_efficiency: float = Field(..., gt=0.0, le=1.0)
    dc_ac_ratio: float = Field(..., gt=0.0)
    clipped_hours: int = Field(..., ge=0)
    clipping_loss_kwh: float = Field(..., ge=0.0)
    is_aggressive_ratio: bool


def apply_clipping(
    *,
    hourly_dc_kw: list[float],
    inverter_ac_kw: float,
    inverter_efficiency: float = DEFAULT_INVERTER_EFFICIENCY,
    dc_kw_nameplate: float | None = None,
    aggressive_ratio_threshold: float = AGGRESSIVE_RATIO_THRESHOLD,
) -> ClippingResult:
    """Convert an hourly DC array into a clipped hourly AC array.

    Each hour: ``ac = min(dc * eta, inverter_ac_kw)``. The clipping
    loss is the integral over hours where ``dc * eta`` exceeded the
    inverter, expressed as kWh of *AC* output forgone (not DC — the
    audit reports what the homeowner doesn't see at the meter).

    ``dc_kw_nameplate`` is optional: when supplied, the result reports
    the nameplate DC:AC ratio for the audit flag. When omitted, the
    ratio is computed from the per-hour DC max as a proxy — useful
    when the caller has a derated array but doesn't know the
    nameplate. The two diverge by the post-derate factor (~14 %).
    """
    if not hourly_dc_kw:
        raise ValueError("hourly_dc_kw must be non-empty")
    if inverter_ac_kw <= 0:
        raise ValueError("inverter_ac_kw must be > 0")
    if not 0.0 < inverter_efficiency <= 1.0:
        raise ValueError("inverter_efficiency must be in (0, 1]")

    if any(dc < 0.0 for dc in hourly_dc_kw):
        raise ValueError("hourly_dc_kw entries must be >= 0")

    hourly_ac_kw: list[float] = []
    clipped_hours = 0
    clipping_loss_kwh = 0.0
    for dc_kw in hourly_dc_kw:
        unclipped_ac = dc_kw * inverter_efficiency
        if unclipped_ac > inverter_ac_kw:
            ac_kw = inverter_ac_kw
            clipped_hours += 1
            clipping_loss_kwh += unclipped_ac - inverter_ac_kw
        else:
            ac_kw = unclipped_ac
        hourly_ac_kw.append(ac_kw)

    if dc_kw_nameplate is None:
        dc_kw_nameplate = max(hourly_dc_kw)
    if dc_kw_nameplate <= 0:
        raise ValueError("dc_kw_nameplate must be > 0 when provided")
    dc_ac_ratio = dc_kw_nameplate / inverter_ac_kw

    return ClippingResult(
        hourly_ac_kw=hourly_ac_kw,
        inverter_ac_kw=inverter_ac_kw,
        inverter_efficiency=inverter_efficiency,
        dc_ac_ratio=dc_ac_ratio,
        clipped_hours=clipped_hours,
        clipping_loss_kwh=clipping_loss_kwh,
        is_aggressive_ratio=dc_ac_ratio > aggressive_ratio_threshold,
    )

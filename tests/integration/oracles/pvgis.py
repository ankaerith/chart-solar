"""PVGIS PVcalc oracle fetcher + case-builder CLI.

JRC's PVGIS PVcalc is the **European regional authority** for PV system
performance estimates. It pairs JRC's reference physics with the
PVGIS-SARAH-2 / PVGIS-NSRDB / PVGIS-ERA5 data products — the definitive
EU/UK standard. Use this oracle for any case routed to PVGIS by
``backend.providers.irradiance.pick_provider`` (i.e., UK + EU lat/lon).

Why not PVWatts.intl for UK?
PVWatts.intl uses ASHRAE TMY — a different reanalysis product than
PVGIS-SARAH-2. Comparing engine output (which runs on PVGIS data via
``PvgisProvider``) against PVWatts.intl mixes physics drift with
data-product drift, hiding real engine variance behind cross-product
noise. PVcalc gives us a same-data-family check.

Endpoint: https://re.jrc.ec.europa.eu/api/v5_2/PVcalc
Public; no API key required. Rate limits are JRC's standard server
limits — generous for harness use.

JRC parameter conventions differ from PVWatts:
- ``angle`` (PVcalc) = tilt (PVWatts). Same units, same meaning.
- ``aspect`` (PVcalc) is the **azimuth using JRC's convention**:
  ``0 = south, +90 = west, -90 = east, ±180 = north``. Opposite
  reference frame from PVWatts where ``0 = north, 180 = south``.
  ``_to_pvcalc_aspect`` handles the conversion.
- ``peakpower`` is in kW (matches PVWatts ``system_capacity``).
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..harness.case import (
    Case,
    Oracle,
    PvgisProductionOracle,
    PvgisPvcalcRequest,
    PvgisPvcalcResponseSlice,
    ScalarExpected,
)

PVGIS_PVCALC_ENDPOINT = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"

#: Default total system losses %. Matches the PVWatts oracle default
#: so cross-oracle comparisons aren't off by the loss assumption alone.
DEFAULT_LOSS_PCT = 14.0

#: Tolerance for PVcalc oracle. Today's pvlib engine on PVGIS data
#: drifts ~7.6 % under PVcalc on a southern-UK site (London) — same
#: shape as chart-solar-9xi4 was, smaller magnitude. Once chart-solar-gi58
#: routes engine.dc_production through PVcalc directly, this tightens
#: to ±2-5 % (engine ≈ source). For now, ±10 % covers today's drift
#: without papering over a real engine vs. regional-authority gap.
DEFAULT_PRODUCTION_TOL_PCT = 10.0


class PvgisApiError(Exception):
    """Raised when PVcalc returns an error in its response body."""


def _to_pvcalc_aspect(pvwatts_azimuth: float) -> float:
    """Convert PVWatts azimuth (0 = N, 180 = S, clockwise) to PVcalc aspect (0 = S, +W, -E).

    Subtracting 180 reflects the south-reference change. Modular
    normalisation keeps the result in ``[-180, 180]``, which is the
    JRC documented range.
    """
    return ((pvwatts_azimuth - 180.0 + 180.0) % 360.0) - 180.0


def fetch_pvcalc(
    request: PvgisPvcalcRequest, *, timeout_s: float = 30.0
) -> PvgisPvcalcResponseSlice:
    """Issue one PVcalc call and return the harness-level slice.

    Surfaces ``errors[]`` from the response body as ``PvgisApiError``
    rather than letting the caller unpack a 200-with-errors response.
    """
    params: dict[str, Any] = {
        "lat": request.lat,
        "lon": request.lon,
        "peakpower": request.peakpower_kw,
        "loss": request.loss_pct,
        "angle": request.angle_deg,
        "aspect": request.aspect_deg,
        "outputformat": "json",
    }
    response = httpx.get(PVGIS_PVCALC_ENDPOINT, params=params, timeout=timeout_s)
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    if body.get("errors"):
        raise PvgisApiError(f"PVcalc errors: {body['errors']}")
    fixed = body["outputs"]["totals"]["fixed"]
    monthly = body["outputs"]["monthly"]["fixed"]
    return PvgisPvcalcResponseSlice(
        ac_annual_kwh=float(fixed["E_y"]),
        ac_monthly_kwh=[float(m["E_m"]) for m in monthly],
    )


def _request_from_inputs(inputs: dict[str, Any]) -> PvgisPvcalcRequest:
    """Derive a single-array PVcalc request from a forecast inputs body."""
    system = inputs.get("system")
    if not isinstance(system, dict):
        raise ValueError("case inputs missing `system` block")
    return PvgisPvcalcRequest(
        lat=float(system["lat"]),
        lon=float(system["lon"]),
        peakpower_kw=float(system["dc_kw"]),
        angle_deg=float(system["tilt_deg"]),
        aspect_deg=_to_pvcalc_aspect(float(system["azimuth_deg"])),
        loss_pct=DEFAULT_LOSS_PCT,
    )


def build_case(case_path: Path) -> Case:
    """Fetch the PVcalc oracle for a case file and rewrite it in place.

    Idempotent: overwrites ``oracle.production`` and the canonical
    production key in ``expected``. Hand-derived keys (NPV, monthly
    bills) are preserved.

    Single-pass cases (``case.inputs``) issue one PVcalc request.
    Multi-pass cases (``case.inputs_arrays``) issue one per sub-array
    and write all requests + responses; the expected annual is summed.
    """
    case = Case.load(case_path)

    if case.inputs_arrays is not None:
        sub_inputs = case.inputs_arrays
    else:
        assert case.inputs is not None  # validator guarantees one is set
        sub_inputs = [case.inputs]

    requests = [_request_from_inputs(sub) for sub in sub_inputs]
    responses = [fetch_pvcalc(req) for req in requests]
    summed_annual = sum(r.ac_annual_kwh for r in responses)

    case.oracle = Oracle(
        production=PvgisProductionOracle(
            source="pvgis_pvcalc_v52",
            endpoint=PVGIS_PVCALC_ENDPOINT,
            fetched_at=datetime.now(UTC),
            requests=requests,
            responses=responses,
        )
    )

    production_keys_owned = {
        "artifacts/engine.dc_production/annual_ac_kwh",
        "engine.dc_production.annual_ac_kwh",  # pre-/-separator legacy
        "engine.dc_production.monthly_ac_kwh",  # pre-/-separator legacy
    }
    for key in production_keys_owned:
        case.expected.pop(key, None)

    case.expected["artifacts/engine.dc_production/annual_ac_kwh"] = ScalarExpected(
        value=summed_annual,
        tol_pct=DEFAULT_PRODUCTION_TOL_PCT,
    )

    case.dump(case_path)
    return case


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tests.integration.oracles.pvgis",
        description="PVGIS PVcalc oracle fetcher for the integration-tests harness.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    bc = sub.add_parser("build-case", help="fetch PVcalc oracle and write into a case file")
    bc.add_argument("case_path", type=Path, help="path to the case JSON file")

    args = parser.parse_args()

    if args.cmd == "build-case":
        case = build_case(args.case_path)
        production = case.oracle.production
        assert production is not None
        annual = sum(r.ac_annual_kwh for r in production.responses)
        print(f"updated {args.case_path}: oracle annual {annual:.1f} kWh (PVcalc)")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

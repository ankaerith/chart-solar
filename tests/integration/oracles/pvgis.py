"""PVGIS PVcalc oracle fetcher + case-builder CLI.

JRC's PVGIS PVcalc is the European regional authority for PV system
performance estimates. Pairs JRC reference physics with PVGIS-SARAH-2
/ -NSRDB / -ERA5 data — the same data product family our engine
consumes via ``PvgisProvider`` — so cross-impl drift is the
meaningful signal.

PVWatts.intl is *not* the right oracle for UK/EU: it uses ASHRAE TMY,
a different reanalysis product. Comparing engine output (PVGIS data)
against PVWatts.intl mixes physics drift with cross-data-product
drift and hides real engine variance behind that noise.

Endpoint: ``https://re.jrc.ec.europa.eu/api/v5_2/PVcalc``. Public API,
no key required.

JRC parameter conventions differ from PVWatts. ``angle`` = tilt (same
units), ``peakpower`` = system DC kW (same), but ``aspect`` is the
azimuth in JRC's south-referenced convention: ``0 = south, +90 = west,
−90 = east, ±180 = north`` — opposite of PVWatts where ``0 = north,
180 = south``. ``_to_pvcalc_aspect`` handles the conversion.
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
)
from ._base import expand_sub_inputs, fetch_concurrent, system_block, write_production_expected

PVGIS_PVCALC_ENDPOINT = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"

#: Total system losses %. Matches the PVWatts default so cross-oracle
#: comparisons aren't off by the loss assumption alone.
DEFAULT_LOSS_PCT = 14.0

#: Provisional ±10 %; tightens once chart-solar-gi58 routes the engine
#: through PVcalc directly (engine ≈ source).
DEFAULT_PRODUCTION_TOL_PCT = 10.0


class PvgisApiError(Exception):
    """Raised when PVcalc returns an error in its response body."""


def _to_pvcalc_aspect(pvwatts_azimuth: float) -> float:
    """Convert PVWatts azimuth (0 = N, 180 = S, clockwise) to PVcalc aspect (0 = S, +W, -E)."""
    return (pvwatts_azimuth % 360.0) - 180.0


def fetch_pvcalc(
    request: PvgisPvcalcRequest, *, timeout_s: float = 30.0
) -> PvgisPvcalcResponseSlice:
    """Issue one PVcalc call and return the harness-level slice.

    Surfaces ``errors[]`` from the response body as ``PvgisApiError``
    rather than letting a 200-with-errors response slip through.
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
    system = system_block(inputs)
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
    """
    case = Case.load(case_path)
    requests = [_request_from_inputs(sub) for sub in expand_sub_inputs(case)]
    responses = fetch_concurrent(fetch_pvcalc, requests)

    case.oracle = Oracle(
        production=PvgisProductionOracle(
            endpoint=PVGIS_PVCALC_ENDPOINT,
            fetched_at=datetime.now(UTC),
            requests=requests,
            responses=responses,
        )
    )
    write_production_expected(
        case,
        annual_kwh=sum(r.ac_annual_kwh for r in responses),
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

    case = build_case(args.case_path)
    production = case.oracle.production
    assert production is not None
    annual = sum(r.ac_annual_kwh for r in production.responses)
    print(f"updated {args.case_path}: oracle annual {annual:.1f} kWh (PVcalc)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

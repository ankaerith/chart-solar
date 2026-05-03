"""PVWatts v8 oracle fetcher + case-builder CLI.

Wraps NREL's PVWatts v8 API as the regional reference for CONUS cases.
Pairs PVWatts physics with NSRDB-family TMY data — the same data
family our engine consumes via ``NsrdbProvider`` — so cross-impl drift
is the meaningful signal. ~3-5 % drift between PVWatts (Fortran) and
pvlib (Python's port of the same algorithm) is the expected baseline.

Endpoint: ``https://developer.nlr.gov/api/pvwatts/v8.json``. NREL
migrated from ``developer.nrel.gov``; the old host still 301-redirects
but we hit the new domain directly.

For UK/EU sites use ``oracles.pvgis`` (JRC PVcalc) — that's the EU
regional authority and pairs JRC physics with PVGIS data. PVWatts.intl
falls back to ASHRAE TMY which is a different data product than what
the engine consumes for non-CONUS, so it's the right oracle only for
rest-of-world (no clear regional authority).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .._env import load_dotenv
from ..harness.case import (
    Case,
    Oracle,
    PvwattsProductionOracle,
    PvwattsRequest,
    PvwattsResponseSlice,
)
from ._base import expand_sub_inputs, fetch_concurrent, system_block, write_production_expected

PVWATTS_ENDPOINT = "https://developer.nlr.gov/api/pvwatts/v8.json"

#: PVWatts module/array/loss defaults that match what NREL's web UI
#: ships as residential roof-mount baseline. Cases override per-system.
DEFAULT_MODULE_TYPE = 0  # 0 = standard, 1 = premium, 2 = thin-film
DEFAULT_ARRAY_TYPE = 1  # 1 = fixed roof mount (residential)
DEFAULT_LOSSES_PCT = 14.0  # PVWatts canonical default (wiring + soiling + age + …)

#: CONUS pairs PVWatts.tmy3 with pvlib-on-NSRDB — same data product
#: family; ±5 % is achievable. Non-CONUS pairs PVWatts.intl (ASHRAE
#: TMY) with pvlib-on-PVGIS — two unrelated reanalysis products with
#: known mid-single-digit drift in cloudy/temperate climates.
DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_CONUS = 5.0
DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_INTL = 10.0


class PvwattsApiError(Exception):
    """Raised when PVWatts returns an error in its response body."""


def fetch_pvwatts(
    api_key: str,
    request: PvwattsRequest,
    *,
    timeout_s: float = 30.0,
) -> PvwattsResponseSlice:
    """Issue one PVWatts v8 call and return the slice the harness compares.

    Surfaces ``errors[]`` from the response body as ``PvwattsApiError``
    rather than letting a 200-with-errors response slip through. Rate
    limits surface as 429 via ``raise_for_status``.
    """
    params: dict[str, Any] = {
        "api_key": api_key,
        "lat": request.lat,
        "lon": request.lon,
        "system_capacity": request.system_capacity_kw,
        "azimuth": request.azimuth,
        "tilt": request.tilt,
        "array_type": request.array_type,
        "module_type": request.module_type,
        "losses": request.losses_pct,
        "dataset": request.dataset,
        "timeframe": "monthly",
    }
    response = httpx.get(PVWATTS_ENDPOINT, params=params, timeout=timeout_s)
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    if body.get("errors"):
        raise PvwattsApiError(f"PVWatts errors: {body['errors']}")
    outputs = body["outputs"]
    return PvwattsResponseSlice(
        ac_annual_kwh=float(outputs["ac_annual"]),
        ac_monthly_kwh=[float(v) for v in outputs["ac_monthly"]],
    )


def _select_dataset(lat: float, lon: float) -> str:
    """Auto-route the PVWatts ``dataset`` parameter.

    Deliberately tighter than ``backend.providers.irradiance._is_us``:
    PVWatts ``tmy3`` data covers CONUS only (Alaska / Hawaii hit 422),
    while NSRDB also covers AK + HI. The two boxes purposely differ.
    """
    is_conus = 24.0 <= lat <= 49.5 and -125.0 <= lon <= -66.5
    return "tmy3" if is_conus else "intl"


def _request_from_inputs(inputs: dict[str, Any]) -> PvwattsRequest:
    system = system_block(inputs)
    lat = float(system["lat"])
    lon = float(system["lon"])
    return PvwattsRequest(
        lat=lat,
        lon=lon,
        system_capacity_kw=float(system["dc_kw"]),
        azimuth=float(system["azimuth_deg"]),
        tilt=float(system["tilt_deg"]),
        array_type=DEFAULT_ARRAY_TYPE,
        module_type=DEFAULT_MODULE_TYPE,
        losses_pct=DEFAULT_LOSSES_PCT,
        dataset=_select_dataset(lat, lon),
    )


def build_case(case_path: Path, api_key: str) -> Case:
    """Fetch the oracle for a case file and rewrite it in place.

    Idempotent: overwrites the existing ``oracle`` block and the
    canonical production entry in ``expected``. Re-run on demand;
    the case file's git diff is the audit trail.
    """
    case = Case.load(case_path)
    requests = [_request_from_inputs(sub) for sub in expand_sub_inputs(case)]
    responses = fetch_concurrent(lambda req: fetch_pvwatts(api_key, req), requests)

    case.oracle = Oracle(
        production=PvwattsProductionOracle(
            endpoint=PVWATTS_ENDPOINT,
            fetched_at=datetime.now(UTC),
            requests=requests,
            responses=responses,
        )
    )
    tol_pct = (
        DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_CONUS
        if requests[0].dataset == "tmy3"
        else DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_INTL
    )
    write_production_expected(
        case,
        annual_kwh=sum(r.ac_annual_kwh for r in responses),
        tol_pct=tol_pct,
    )
    case.dump(case_path)
    return case


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tests.integration.oracles.pvwatts",
        description="PVWatts v8 oracle fetcher for the integration-tests harness.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    bc = sub.add_parser("build-case", help="fetch PVWatts oracle and write into a case file")
    bc.add_argument("case_path", type=Path, help="path to the case JSON file")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    api_key = os.environ.get("NREL_API_KEY")
    if not api_key:
        print(
            "error: NREL_API_KEY not set in environment or .env at repo root",
            file=sys.stderr,
        )
        return 2

    case = build_case(args.case_path, api_key)
    production = case.oracle.production
    assert production is not None
    annual = sum(r.ac_annual_kwh for r in production.responses)
    print(f"updated {args.case_path}: oracle annual {annual:.1f} kWh")
    return 0


if __name__ == "__main__":
    sys.exit(main())

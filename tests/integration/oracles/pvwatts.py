"""PVWatts v8 oracle fetcher + case-builder CLI.

Wraps NREL's PVWatts v8 API as a reference oracle for `engine.dc_production`.
PVWatts is the same algorithm pvlib's `ModelChain.with_pvwatts` runs in
our engine — different implementation (NREL Fortran vs. pvlib Python).
That makes it a cross-implementation check on production, not a
cross-algorithm one; ~3-5 % drift between the two is expected and
the case tolerance bands reflect that.

Endpoint: ``https://developer.nlr.gov/api/pvwatts/v8.json``. NREL
migrated from ``developer.nrel.gov``; the old host still 301-redirects
but we skip the round-trip by hitting the new domain directly.

Single-array today. Multi-array support (one PVWatts call per
sub-array, summed AC) is part of issue chart-solar-90dz's deferred
work and lands alongside the Seattle 2-pass case.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..harness.case import (
    Case,
    Oracle,
    PvwattsProductionOracle,
    PvwattsRequest,
    PvwattsResponseSlice,
    ScalarExpected,
)

PVWATTS_ENDPOINT = "https://developer.nlr.gov/api/pvwatts/v8.json"

#: PVWatts module/array/loss defaults that match what NREL's web UI
#: ships as residential roof-mount baseline. Cases override per-system.
DEFAULT_MODULE_TYPE = 0  # 0 = standard, 1 = premium, 2 = thin-film
DEFAULT_ARRAY_TYPE = 1  # 1 = fixed roof mount (residential)
DEFAULT_LOSSES_PCT = 14.0  # PVWatts canonical default (wiring + soiling + age + …)

#: Tolerance bands the case-builder writes into ``expected`` by default.
#: Annual is tighter than monthly because monthly-shape drift between
#: two PVWatts implementations (or weather-year edge cases) is larger
#: than the annual roll-up. Override per case if needed.
#:
#: CONUS uses ``tmy3`` (PVWatts) vs pvlib-on-NSRDB (engine) — same
#: data product family; 5 % is achievable. Non-CONUS uses ``intl``
#: (PVWatts: ASHRAE TMY) vs pvlib-on-PVGIS (engine: JRC SARAH/ERA5)
#: — two unrelated reanalysis products with known mid-single-digit
#: drift in cloudy/temperate climates. 10 % captures that without
#: hiding real engine regressions.
DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_CONUS = 5.0
DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_INTL = 10.0
DEFAULT_PRODUCTION_TOL_MONTHLY_PCT = 8.0


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
    rather than letting the caller unpack a 200-with-errors response
    silently. Rate limits surface as 429 via ``raise_for_status``.
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
    """PVWatts dataset selection — auto-route based on lat/lon.

    ``tmy3`` is CONUS-only (PVWatts uses ~1020 NSRDB TMY3 weather
    stations in the contiguous US). For everywhere else — Alaska,
    Hawaii, UK, EU, rest of world — ``intl`` falls back to
    NSRDB-International / ASHRAE TMY data: global coverage at a
    coarser grid.

    Note: this picks the *oracle* data source, not the engine's. The
    engine reads from its own irradiance providers (NSRDB → PVGIS →
    Open-Meteo) per ``backend.providers.irradiance.pick_provider``.
    Cross-implementation drift between PVWatts.intl (ASHRAE TMY) and
    PVGIS (JRC SARAH/ERA5) is wider than the CONUS PVWatts.tmy3 ↔
    pvlib-on-NSRDB drift, so non-CONUS cases may need a wider
    tolerance.
    """
    is_conus = 24.0 <= lat <= 49.5 and -125.0 <= lon <= -66.5
    return "tmy3" if is_conus else "intl"


def _request_from_inputs(inputs: dict[str, Any]) -> PvwattsRequest:
    """Derive a single-array PVWatts request from a forecast inputs body."""
    system = inputs.get("system")
    if not isinstance(system, dict):
        raise ValueError("case inputs missing `system` block")
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

    Idempotent: overwrites the existing ``oracle`` block and any
    production entries in ``expected``. Re-run on demand when PVWatts
    publishes a new TMY3 dataset version or the case's geometry
    changes — the case file's git diff is the audit trail.

    Single-pass cases (``case.inputs``) issue one PVWatts request.
    Multi-pass cases (``case.inputs_arrays``) issue one per sub-array
    and write all requests + responses into the oracle so the case
    file is reproducible end-to-end. The expected annual is the
    summed annual across sub-arrays.
    """
    case = Case.load(case_path)

    if case.inputs_arrays is not None:
        sub_inputs = case.inputs_arrays
    else:
        assert case.inputs is not None  # validator guarantees one is set
        sub_inputs = [case.inputs]

    requests = [_request_from_inputs(sub) for sub in sub_inputs]
    responses = [fetch_pvwatts(api_key, req) for req in requests]
    summed_annual = sum(r.ac_annual_kwh for r in responses)

    # Pick tolerance from the dataset of the first request — multi-pass
    # cases at the same lat/lon all use the same dataset; a future
    # cross-region multi-pass case would need a more careful rule, but
    # we don't have one yet.
    tol_pct = (
        DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_CONUS
        if requests[0].dataset == "tmy3"
        else DEFAULT_PRODUCTION_TOL_ANNUAL_PCT_INTL
    )

    case.oracle = Oracle(
        production=PvwattsProductionOracle(
            source="pvwatts_v8",
            endpoint=PVWATTS_ENDPOINT,
            fetched_at=datetime.now(UTC),
            requests=requests,
            responses=responses,
        )
    )

    # Production-related expected keys this builder owns. Wipe before
    # writing so re-running over a case file doesn't accumulate stale
    # entries (e.g., legacy dotted-path keys from earlier harness
    # versions). Other keys — hand-derived NPV, monthly bills — are
    # preserved.
    production_keys_owned = {
        "artifacts/engine.dc_production/annual_ac_kwh",
        "engine.dc_production.annual_ac_kwh",  # pre-/-separator legacy
        "engine.dc_production.monthly_ac_kwh",  # pre-/-separator legacy
    }
    for key in production_keys_owned:
        case.expected.pop(key, None)

    # Slash-separated path: walks ``result.artifacts``, then the literal
    # feature key ``engine.dc_production`` (which contains dots — that's
    # why the comparator's path syntax uses ``/`` rather than ``.``).
    # For multi-pass cases the engine outputs are summed in-harness
    # before reaching the comparator (see ``_merge_dc_production``),
    # so this path resolves the same way for single- and multi-pass.
    case.expected["artifacts/engine.dc_production/annual_ac_kwh"] = ScalarExpected(
        value=summed_annual,
        tol_pct=tol_pct,
    )
    # Monthly comparison is deferred: the engine emits ``hourly_ac_kw``
    # (8760-long), not a 12-vector, so a direct comparison would need
    # an hourly→monthly aggregator in the comparator. PVWatts oracle
    # data is preserved on ``case.oracle`` for when that lands.

    case.dump(case_path)
    return case


def _resolve_api_key() -> str | None:
    """Process env wins; fall back to a minimal ``.env`` scrape at the repo root."""
    key = os.environ.get("NREL_API_KEY")
    if key:
        return key
    repo_root = Path(__file__).resolve().parents[3]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return None
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line.startswith("NREL_API_KEY="):
            continue
        _, _, value = line.partition("=")
        return value.strip().strip('"').strip("'")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tests.integration.oracles.pvwatts",
        description="PVWatts v8 oracle fetcher for the integration-tests harness.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    bc = sub.add_parser("build-case", help="fetch PVWatts oracle and write into a case file")
    bc.add_argument("case_path", type=Path, help="path to the case JSON file")

    args = parser.parse_args()

    api_key = _resolve_api_key()
    if not api_key:
        print(
            "error: NREL_API_KEY not set in environment or .env at repo root",
            file=sys.stderr,
        )
        return 2

    if args.cmd == "build-case":
        case = build_case(args.case_path, api_key)
        production = case.oracle.production
        assert production is not None  # build_case always populates it
        annual = production.responses[0].ac_annual_kwh
        print(f"updated {args.case_path}: oracle annual {annual:.1f} kWh")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

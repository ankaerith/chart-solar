"""CLI entrypoint for the integration-tests harness.

Run with:

    uv run python -m tests.integration.harness.run [--case NAME] [--validate-only]

Reads `API_BASE_URL` and any oracle keys from `.env` at the repo root
(via a stdlib loader — no python-dotenv dep) plus the process env.
Loads case files from ``tests/integration/cases/``, runs each through
the API, and prints a per-metric pass/fail report. Exits non-zero if
any case fails — suitable for CI gating once we wire it.

Stack-boot is the user's responsibility (`docker compose up`); the
harness fails loudly if `API_BASE_URL` is unreachable rather than
trying to spawn services itself.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from .._env import load_dotenv
from .case import Case, ScalarExpected, load_cases
from .client import ForecastFailedError, ForecastTimeoutError, run_case
from .compare import CaseReport, MetricResult, compare

#: Default location of the case directory, relative to this file.
DEFAULT_CASES_DIR = Path(__file__).resolve().parent.parent / "cases"

#: Default API target. Overridable via ``--api-base-url`` or the
#: ``API_BASE_URL`` env var; the env var wins over the default but
#: loses to an explicit CLI flag (argparse's normal precedence).
DEFAULT_API_BASE_URL = "http://localhost:8000"

#: Default per-job poll budget. The forecast worker is expected to
#: finish in well under a minute for a single 8760-hour case; bumping
#: to 120s leaves headroom for cold-start + Monte Carlo.
DEFAULT_TIMEOUT_S = 120.0


def _format_report(report: CaseReport) -> str:
    lines: list[str] = []
    badge = "PASS" if report.passed else "FAIL"
    lines.append(f"[{badge}] {report.case.name}")
    for m in report.metrics:
        flag = "  ✓" if m.passed else "  ✗"
        lines.append(f"{flag} {m.path}: {m.detail}")
    return "\n".join(lines)


async def _run_one(
    client: httpx.AsyncClient, base_url: str, case: Case, timeout_s: float
) -> CaseReport:
    if case.inputs_arrays is not None:
        return await _run_multi_pass(client, base_url, case, timeout_s)
    assert case.inputs is not None  # validator guarantees exactly one is set
    try:
        body = await run_case(client, base_url, case.inputs, timeout_s=timeout_s)
    except ForecastTimeoutError as exc:
        return _synthesize_fail(case, f"timeout: {exc}")
    except ForecastFailedError as exc:
        return _synthesize_fail(case, f"job failed: {exc}")
    except httpx.HTTPError as exc:
        return _synthesize_fail(case, f"HTTP error: {exc}")
    return compare(case, body)


async def _run_multi_pass(
    client: httpx.AsyncClient, base_url: str, case: Case, timeout_s: float
) -> CaseReport:
    """Submit each sub-array's inputs, sum production, compare summed result.

    Workaround for cases like Seattle (4.4 kW N + 16.28 kW S) where the
    real system spans multiple arrays but the engine's ``SystemInputs``
    is single-array (chart-solar-h3y6). Each entry in ``inputs_arrays``
    is a complete forecast body; we run them serially (idempotency
    keys are body-hashed, so distinct bodies don't collide), then
    element-wise-sum hourly_ac_kw and total annual_ac_kwh into a
    synthetic ``engine.dc_production`` block for the comparator.
    """
    assert case.inputs_arrays is not None  # _run_one branched on this
    bodies: list[dict[str, Any]] = []
    for sub_inputs in case.inputs_arrays:
        try:
            body = await run_case(client, base_url, sub_inputs, timeout_s=timeout_s)
        except ForecastTimeoutError as exc:
            return _synthesize_fail(case, f"sub-array timeout: {exc}")
        except ForecastFailedError as exc:
            return _synthesize_fail(case, f"sub-array failed: {exc}")
        except httpx.HTTPError as exc:
            return _synthesize_fail(case, f"sub-array HTTP error: {exc}")
        bodies.append(body)
    return compare(case, _merge_dc_production(bodies))


def _merge_dc_production(bodies: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a synthetic forecast result whose ``engine.dc_production``
    sums hourly + annual AC across N sub-array runs.

    Only the production block is summed — other artifacts (snow,
    finance, tariff) don't have a sensible per-array decomposition
    in the multi-pass workaround, so they're omitted from the
    synthetic result. Cases with multi-pass inputs should only assert
    on production paths until chart-solar-h3y6 lands.
    """
    dc_blocks = [b["result"]["artifacts"]["engine.dc_production"] for b in bodies]
    hourly_lists = [d["hourly_ac_kw"] for d in dc_blocks]
    summed_hourly = [sum(values) for values in zip(*hourly_lists, strict=True)]
    summed_annual = sum(d["annual_ac_kwh"] for d in dc_blocks)
    return {
        "result": {
            "artifacts": {
                "engine.dc_production": {
                    "annual_ac_kwh": summed_annual,
                    "hourly_ac_kw": summed_hourly,
                }
            }
        }
    }


def _synthesize_fail(case: Case, detail: str) -> CaseReport:
    """Build a single-metric failing report when the run never produced a result.

    Lets the report-printing path stay uniform — every case turns
    into a CaseReport, pass or fail, regardless of whether the API
    even returned.
    """
    sentinel = MetricResult("<run>", ScalarExpected(value=0.0, tol_pct=0.0), None, False, detail)
    return CaseReport(case=case, metrics=[sentinel])


async def _run_all(cases: list[Case], base_url: str, timeout_s: float) -> list[CaseReport]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        return [await _run_one(client, base_url, c, timeout_s) for c in cases]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tests.integration.harness.run",
        description="Black-box integration tests against the forecast API.",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("API_BASE_URL", DEFAULT_API_BASE_URL),
        help=f"API base URL (default {DEFAULT_API_BASE_URL}; or $API_BASE_URL).",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=DEFAULT_CASES_DIR,
        help="directory containing case JSON files.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=None,
        help="run only the named case(s); repeatable. Default: all.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"per-case wall-clock budget in seconds (default {DEFAULT_TIMEOUT_S}).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="load and validate cases without hitting the API.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    load_dotenv(repo_root / ".env")

    try:
        cases = load_cases(args.cases_dir, args.case)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not cases:
        print(
            f"no cases found in {args.cases_dir}" + (f" matching {args.case}" if args.case else "")
        )
        return 0

    if args.validate_only:
        for c in cases:
            print(f"  ok: {c.name}")
        print(f"\nvalidated {len(cases)} cases")
        return 0

    reports = asyncio.run(_run_all(cases, args.api_base_url, args.timeout))
    failed = 0
    for r in reports:
        print(_format_report(r))
        print()
        if not r.passed:
            failed += 1

    summary = f"{len(reports) - failed}/{len(reports)} passed"
    print(summary)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

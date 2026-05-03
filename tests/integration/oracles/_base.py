"""Shared helpers used by every oracle's case-builder.

Each oracle (PVWatts, PVGIS PVcalc, future PySAM) does the same
high-level dance: load the case, expand single- or multi-pass inputs,
fetch references in parallel, write the production expected. Keeping
that scaffold here lets each oracle module shrink to its API-specific
parts.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..harness.case import Case, ScalarExpected

#: Production-related ``expected`` keys that any oracle's ``build_case``
#: wipes before writing. Includes legacy dotted-path keys from earlier
#: harness versions so re-runs over a case file don't accumulate
#: stale entries.
PRODUCTION_KEYS_OWNED = frozenset(
    {
        "artifacts/engine.dc_production/annual_ac_kwh",
        "engine.dc_production.annual_ac_kwh",
        "engine.dc_production.monthly_ac_kwh",
    }
)


def system_block(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract the canonical ``inputs.system`` dict or raise."""
    system = inputs.get("system")
    if not isinstance(system, dict):
        raise ValueError("case inputs missing `system` block")
    return system


def expand_sub_inputs(case: Case) -> list[dict[str, Any]]:
    """Multi-pass cases expose ``inputs_arrays``; single-pass wraps ``inputs`` in a list."""
    if case.inputs_arrays is not None:
        return case.inputs_arrays
    assert case.inputs is not None  # case validator guarantees one is set
    return [case.inputs]


def fetch_concurrent[T, R](fetch: Callable[[T], R], items: list[T]) -> list[R]:
    """Run ``fetch`` over each item, preserving order.

    Threads (not asyncio) keep oracle modules sync-only. For a
    multi-pass case with N sub-arrays the wall-clock collapses from
    ``N × per-call`` to ``max(per-call)``; PVWatts and PVcalc both
    tolerate the modest concurrency these case-builders generate.
    """
    if len(items) == 1:
        return [fetch(items[0])]
    with ThreadPoolExecutor(max_workers=len(items)) as pool:
        return list(pool.map(fetch, items))


def write_production_expected(case: Case, annual_kwh: float, tol_pct: float) -> None:
    """Replace any existing production expected with the canonical entry."""
    for key in PRODUCTION_KEYS_OWNED:
        case.expected.pop(key, None)
    case.expected["artifacts/engine.dc_production/annual_ac_kwh"] = ScalarExpected(
        value=annual_kwh,
        tol_pct=tol_pct,
    )

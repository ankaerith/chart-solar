"""Pydantic schema for integration-test case files.

A case file pairs a `ForecastInputs` body (POSTed to `/api/forecast`)
with reference data from an external oracle (PVWatts v8 today, PySAM
later) and a per-metric expected-value table. The harness POSTs the
inputs, polls for the result, then walks the expected table comparing
actual against expected within each metric's declared tolerance.

Case files are JSON, deliberately. They get committed alongside the
harness so a reviewer can read a case without running it; a
diff-friendly text format makes oracle drift visible in PR review.

Loose `inputs: dict` (not a backend-imported `ForecastInputs`) keeps
the harness genuinely black-box — schema drift on the API surface
must be caught by a real HTTP round-trip, not by an in-process
import that silently picks up the change.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScalarExpected(BaseModel):
    """A single-number expectation, tolerance expressed as ± percent of expected."""

    kind: Literal["scalar"] = "scalar"
    value: float
    tol_pct: float = Field(..., ge=0.0, le=100.0)


class VectorExpected(BaseModel):
    """A vector expectation (e.g., 12 monthly kWh values).

    Tolerance applies element-wise: each `actual[i]` must be within
    ``tol_pct`` percent of ``values[i]``. Length mismatch is a hard
    fail — the comparator does not pad or truncate.
    """

    kind: Literal["vector"] = "vector"
    values: list[float]
    tol_pct: float = Field(..., ge=0.0, le=100.0)


ExpectedMetric = ScalarExpected | VectorExpected


class PvwattsRequest(BaseModel):
    """One PVWatts API call's parameters, frozen for reproducibility.

    Multi-array cases issue N calls (one per sub-array); each is
    recorded so a reader can re-derive the oracle without trusting
    summed numbers blindly.
    """

    lat: float
    lon: float
    system_capacity_kw: float
    azimuth: float
    tilt: float
    array_type: int
    module_type: int
    losses_pct: float
    dataset: str = "tmy3"


class PvwattsResponseSlice(BaseModel):
    """The PVWatts response fields the harness compares against."""

    ac_annual_kwh: float
    ac_monthly_kwh: list[float] = Field(..., min_length=12, max_length=12)


class ProductionOracle(BaseModel):
    """PVWatts-derived production oracle. One request/response pair per sub-array.

    For multi-array cases, downstream code sums ``ac_annual_kwh`` and
    element-wise sums ``ac_monthly_kwh`` across responses to produce
    the system-level oracle.
    """

    source: Literal["pvwatts_v8"]
    endpoint: str
    fetched_at: datetime
    requests: list[PvwattsRequest] = Field(..., min_length=1)
    responses: list[PvwattsResponseSlice] = Field(..., min_length=1)


class Oracle(BaseModel):
    """Container for per-domain oracle data; extends as new oracles land."""

    production: ProductionOracle | None = None


class Case(BaseModel):
    """A complete integration-test case.

    `inputs` is the raw request body passed to ``POST /api/forecast``.
    The harness validates it as ``dict[str, Any]`` so the API itself
    is the contract; a typo in the inputs produces a 422 from FastAPI
    rather than a silent in-process Pydantic miss.
    """

    name: str
    description: str = ""
    inputs: dict[str, Any]
    oracle: Oracle = Field(default_factory=Oracle)
    expected: dict[str, ExpectedMetric] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Case:
        return cls.model_validate_json(path.read_text())

    def dump(self, path: Path) -> None:
        # ensure_ascii=False keeps em-dashes / degree signs human-readable
        # in the committed file rather than as ``—`` escapes.
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
        )


def load_cases(cases_dir: Path, names: list[str] | None = None) -> list[Case]:
    """Load every ``*.json`` case from ``cases_dir`` (or a name-filtered subset).

    Files starting with ``_`` are skipped on a default load — convention
    for samples and templates the harness shouldn't run automatically.
    Naming one explicitly via ``names`` overrides the skip, so
    ``--case _sample`` works for harness debugging.
    """
    files = sorted(cases_dir.glob("*.json"))
    cases = [Case.load(p) for p in files]
    if names:
        wanted = set(names)
        return [c for c in cases if c.name in wanted]
    return [c for c in cases if not c.name.startswith("_")]

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

from pydantic import BaseModel, Field, model_validator


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


class PvgisPvcalcRequest(BaseModel):
    """One PVGIS PVcalc / seriescalc API call's parameters.

    JRC's API conventions differ from PVWatts:
    - ``angle`` (not tilt). Same units, same meaning.
    - ``aspect`` (not azimuth). **Convention is 0 = south, +90 = west,
      −90 = east** — opposite of PVWatts where 0 = north, 180 = south.
      The case-builder converts.
    - ``peakpower`` in kW (not "system_capacity").
    - ``loss`` is total system losses % (broadly equivalent to
      PVWatts's ``losses``).
    """

    lat: float
    lon: float
    peakpower_kw: float
    angle_deg: float
    aspect_deg: float
    loss_pct: float


class PvgisPvcalcResponseSlice(BaseModel):
    """The PVGIS PVcalc response fields the harness compares against.

    PVcalc returns ``E_y`` (annual energy, kWh) and ``E_m`` per month
    (kWh/month) inside ``outputs.totals.fixed`` and
    ``outputs.monthly.fixed`` respectively.
    """

    ac_annual_kwh: float
    ac_monthly_kwh: list[float] = Field(..., min_length=12, max_length=12)


class PvwattsProductionOracle(BaseModel):
    """PVWatts-v8-derived production oracle. One request/response pair per sub-array."""

    source: Literal["pvwatts_v8"] = "pvwatts_v8"
    endpoint: str
    fetched_at: datetime
    requests: list[PvwattsRequest] = Field(..., min_length=1)
    responses: list[PvwattsResponseSlice] = Field(..., min_length=1)


class PvgisProductionOracle(BaseModel):
    """PVGIS-PVcalc-derived production oracle (JRC, the European regional authority).

    Use this for UK/EU cases — it pairs JRC's reference physics with
    JRC's data, the definitive EU standard. PVWatts.intl on the same
    site uses ASHRAE TMY (different data product) and produces wider
    drift that masks real engine-vs-source variance.
    """

    source: Literal["pvgis_pvcalc_v52"] = "pvgis_pvcalc_v52"
    endpoint: str
    fetched_at: datetime
    requests: list[PvgisPvcalcRequest] = Field(..., min_length=1)
    responses: list[PvgisPvcalcResponseSlice] = Field(..., min_length=1)


ProductionOracle = PvwattsProductionOracle | PvgisProductionOracle


class Oracle(BaseModel):
    """Container for per-domain oracle data; extends as new oracles land."""

    production: ProductionOracle | None = Field(default=None, discriminator="source")


class Case(BaseModel):
    """A complete integration-test case.

    Exactly one of ``inputs`` or ``inputs_arrays`` is set:

    - ``inputs`` (dict): single-pass case — body POSTed to ``/api/forecast``
      verbatim, single result compared against ``expected``.
    - ``inputs_arrays`` (list[dict]): multi-pass case — each entry is
      submitted as its own forecast, the harness sums production
      results across runs, then compares the summed result against
      ``expected``. Workaround until ``chart-solar-h3y6`` lands
      multi-array support in ``SystemInputs``; once that does, these
      cases collapse back to single-pass.

    Both forms validate as ``dict[str, Any]`` (not a typed
    ``ForecastInputs``) so the API itself is the contract — a typo
    in the inputs produces a 422 from FastAPI rather than a silent
    in-process Pydantic miss.
    """

    name: str
    description: str = ""
    inputs: dict[str, Any] | None = None
    inputs_arrays: list[dict[str, Any]] | None = None
    oracle: Oracle = Field(default_factory=Oracle)
    expected: dict[str, ExpectedMetric] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exactly_one_inputs_form(self) -> Case:
        if (self.inputs is None) == (self.inputs_arrays is None):
            raise ValueError(
                "Case requires exactly one of `inputs` or `inputs_arrays` (not both / not neither)"
            )
        if self.inputs_arrays is not None and len(self.inputs_arrays) < 2:
            raise ValueError("`inputs_arrays` must have ≥ 2 entries; use `inputs` for single-pass")
        return self

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

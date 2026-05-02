"""Tolerance-aware comparison of expected vs actual case results.

The case file declares `expected: dict[str, ExpectedMetric]` keyed by
slash-separated path into the API response body's ``result`` artifact
tree. Each metric's ``tol_pct`` is interpreted as ± percent of the
expected value, applied scalar-wise (vector expectations apply
tolerance element-by-element).

The path separator is ``/`` rather than ``.`` because the engine's
artifact keys themselves contain dots (``engine.dc_production``,
``engine.snow``, etc.). A path like
``artifacts/engine.dc_production/annual_ac_kwh`` walks into the
artifacts dict, then the literal-dot feature key, then the leaf —
which dotted notation can't unambiguously express.

Why path-string lookup over typed accessors: the engine's artifact
tree is wide (every step writes its own block) and shifting (steps
land per-phase). String paths keep the case file expressive without
coupling the harness to a backend Pydantic model that would need to
be kept in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .case import Case, ExpectedMetric, ScalarExpected, VectorExpected


@dataclass(frozen=True)
class MetricResult:
    """Outcome of one metric's comparison."""

    path: str
    expected: ExpectedMetric
    actual: Any
    passed: bool
    detail: str


@dataclass(frozen=True)
class CaseReport:
    """All metric outcomes for one case, plus aggregate pass/fail."""

    case: Case
    metrics: list[MetricResult]

    @property
    def passed(self) -> bool:
        return all(m.passed for m in self.metrics)


def _walk(tree: Any, path: str) -> Any:
    """Resolve a slash-separated path into a nested dict / list structure.

    Each segment between slashes is matched verbatim — so a segment
    can itself contain dots (``engine.dc_production``) and we look it
    up as a single dict key without further parsing.

    Returns the sentinel string ``"<missing>"`` rather than raising,
    so the comparator produces a clean per-metric "missing" result
    instead of aborting the whole case on the first absent key.
    """
    cursor: Any = tree
    for part in path.split("/"):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        elif isinstance(cursor, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(cursor):
                cursor = cursor[idx]
            else:
                return "<missing>"
        else:
            return "<missing>"
    return cursor


def _within_tolerance(expected: float, actual: float, tol_pct: float) -> bool:
    """Pass if ``|actual - expected| / |expected| <= tol_pct/100``.

    Special case: ``expected == 0`` requires ``actual == 0`` exactly,
    since percent-of-zero is undefined.
    """
    if expected == 0.0:
        return actual == 0.0
    return abs(actual - expected) / abs(expected) <= tol_pct / 100.0


def _compare_scalar(path: str, exp: ScalarExpected, actual: Any) -> MetricResult:
    if not isinstance(actual, (int, float)):
        return MetricResult(
            path, exp, actual, False, f"expected number, got {type(actual).__name__}"
        )
    actual_f = float(actual)
    passed = _within_tolerance(exp.value, actual_f, exp.tol_pct)
    delta_pct = (actual_f - exp.value) / exp.value * 100.0 if exp.value != 0.0 else 0.0
    detail = f"expected {exp.value:.4g} (±{exp.tol_pct}%), got {actual_f:.4g} (Δ {delta_pct:+.2f}%)"
    return MetricResult(path, exp, actual_f, passed, detail)


def _compare_vector(path: str, exp: VectorExpected, actual: Any) -> MetricResult:
    if not isinstance(actual, list):
        return MetricResult(path, exp, actual, False, f"expected list, got {type(actual).__name__}")
    if len(actual) != len(exp.values):
        return MetricResult(
            path,
            exp,
            actual,
            False,
            f"length mismatch: expected {len(exp.values)}, got {len(actual)}",
        )
    failures: list[str] = []
    for i, (e, a) in enumerate(zip(exp.values, actual, strict=True)):
        if not isinstance(a, (int, float)):
            failures.append(f"[{i}] non-numeric ({type(a).__name__})")
            continue
        if not _within_tolerance(e, float(a), exp.tol_pct):
            failures.append(f"[{i}] expected {e:.4g}, got {float(a):.4g}")
    if failures:
        return MetricResult(
            path,
            exp,
            actual,
            False,
            f"{len(failures)} elements out of tolerance: " + "; ".join(failures[:3]),
        )
    return MetricResult(
        path, exp, actual, True, f"all {len(exp.values)} elements within ±{exp.tol_pct}%"
    )


def compare(case: Case, result_body: dict[str, Any]) -> CaseReport:
    """Walk a case's expected table, comparing each entry to the result.

    ``result_body`` is the full ``GET /api/forecast/{id}`` response —
    the artifact tree lives at ``result_body["result"]``. A missing
    ``result`` block is itself a hard fail, surfaced once at the top.
    """
    artifacts = result_body.get("result")
    if artifacts is None:
        sentinel = MetricResult(
            "<top>",
            ScalarExpected(value=0.0, tol_pct=0.0),
            None,
            False,
            "response had no `result` block",
        )
        return CaseReport(case=case, metrics=[sentinel])

    metrics: list[MetricResult] = []
    for path, expected in case.expected.items():
        actual = _walk(artifacts, path)
        if actual == "<missing>":
            metrics.append(MetricResult(path, expected, None, False, "path not present in result"))
            continue
        if isinstance(expected, ScalarExpected):
            metrics.append(_compare_scalar(path, expected, actual))
        elif isinstance(expected, VectorExpected):
            metrics.append(_compare_vector(path, expected, actual))
    return CaseReport(case=case, metrics=metrics)

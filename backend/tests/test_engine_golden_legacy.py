"""Golden cross-validation against the legacy single-user repo.

The fixture (`fixtures/legacy_solar_tracker_2025.json`) is a verbatim
copy of `data/solar_financial_data.json` from
https://github.com/ankaerith/solar-tracker — the predecessor system
this project evolved from. It carries a 25-year per-year cashflow
ledger plus an `npv_summary` block (NPV at 6 % and 8 % over 15 / 20 /
25-year horizons).

These tests pin our `engine.finance.npv` primitive against that ledger:
fed the same year-1..year-N net-cash-flow stream, our NPV reproduces
the legacy summary to floating-point precision. That's an independent
cross-check — the legacy NPV was computed by an unrelated codebase,
and any drift in our discounting math would surface here.

End-to-end pipeline reproduction (running our engine on the same input
parameters and matching the cashflow ledger within 1 %) is intentionally
out of scope here — the legacy stack used PVWatts for production, two
parallel loans, and a marginal-tax-rate input the engine doesn't yet
ingest, so a clean "feed inputs, match outputs" comparison needs more
scaffolding. See `backend/tests/fixtures/README.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.engine.finance import npv

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "legacy_solar_tracker_2025.json"


@pytest.fixture(scope="module")
def legacy_ledger() -> dict[str, object]:
    data: dict[str, object] = json.loads(_FIXTURE_PATH.read_text())
    return data


def _flows_year_one_indexed(ledger: dict[str, object], horizon: int) -> list[float]:
    """Build a flow stream where index 0 is undiscounted (year 0, $0)
    and indices 1..N hold the legacy net cash flow for years 1..N.

    The legacy ledger discounts year 1 by ``(1+r)^1``, year 2 by
    ``(1+r)^2``, etc., with no year-0 outflow — capex and down payment
    are folded into year 1's net_cash_flow. Our `npv()` discounts
    position 0 by ``(1+r)^0`` (i.e., undiscounted), so prepending
    a 0.0 placeholder aligns the indexing.
    """
    projections = ledger["annual_projections"]
    assert isinstance(projections, list)
    flows = [float(p["net_cash_flow"]) for p in projections[:horizon]]
    return [0.0, *flows]


@pytest.mark.parametrize(
    ("horizon", "rate", "summary_key"),
    [
        (15, 0.06, "npv_15yr_6pct"),
        (20, 0.06, "npv_20yr_6pct"),
        (25, 0.06, "npv_25yr_6pct"),
        (15, 0.08, "npv_15yr_8pct"),
        (20, 0.08, "npv_20yr_8pct"),
        (25, 0.08, "npv_25yr_8pct"),
    ],
)
def test_npv_matches_legacy_summary(
    legacy_ledger: dict[str, object],
    horizon: int,
    rate: float,
    summary_key: str,
) -> None:
    """Our discounting math reproduces the legacy NPV summary.

    Tolerance is 1 % per the bead's acceptance bar; in practice the
    match is exact to floating-point precision because both systems
    compute the same closed-form sum.
    """
    summary = legacy_ledger["npv_summary"]
    assert isinstance(summary, dict)
    expected = float(summary[summary_key])
    flows = _flows_year_one_indexed(legacy_ledger, horizon)
    assert npv(rate, flows) == pytest.approx(expected, rel=0.01)


def test_per_year_cumulative_npv_matches_legacy_ledger(
    legacy_ledger: dict[str, object],
) -> None:
    """The legacy ledger carries a running NPV column (`npv_6pct` per
    year) — the cumulative discounted cashflow up through year y.

    Reproducing that column year-by-year is a stricter regression than
    the summary block: an off-by-one in discount-period indexing would
    pass the summary check on cancellation but fail here.
    """
    projections = legacy_ledger["annual_projections"]
    assert isinstance(projections, list)
    for year_index, projection in enumerate(projections, start=1):
        flows = _flows_year_one_indexed(legacy_ledger, year_index)
        expected = float(projection["npv_6pct"])
        assert npv(0.06, flows) == pytest.approx(expected, rel=0.01), (
            f"Year {year_index}: NPV mismatch"
        )

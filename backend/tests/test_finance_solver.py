"""Unit tests for the private root-finders in backend.engine.finance._solver.

The integration tests in ``test_finance_cashflow.py`` exercise these
through ``irr`` / ``dealer_fee_effective_apr``. This module pins the
solver's own behaviour on synthetic objectives so a future Newton-step
addition or convergence-bound tweak doesn't silently degrade the
guarantees IRR depends on.
"""

from __future__ import annotations

import math

import pytest

from backend.engine.finance._solver import _bisect, _brent


def test_bisect_finds_root_of_quadratic() -> None:
    """f(x) = x² − 2 has a root at √2 ≈ 1.4142."""
    root = _bisect(lambda x: x * x - 2.0, 0.0, 2.0)
    assert root == pytest.approx(math.sqrt(2.0), abs=1e-6)


def test_bisect_handles_decreasing_function() -> None:
    """f(x) = 5 − x has a root at x = 5; f is monotonically decreasing.
    The sign-tracking branch must follow the moving endpoint."""
    root = _bisect(lambda x: 5.0 - x, 0.0, 10.0)
    assert root == pytest.approx(5.0, abs=1e-6)


def test_bisect_swaps_low_high_when_passed_reversed() -> None:
    root = _bisect(lambda x: x - 3.0, 10.0, 0.0)
    assert root == pytest.approx(3.0, abs=1e-6)


def test_bisect_respects_target_offset() -> None:
    """target=10 → solve f(x) == 10 → for f(x)=2x, root is x=5."""
    root = _bisect(lambda x: 2.0 * x, 0.0, 100.0, target=10.0)
    assert root == pytest.approx(5.0, abs=1e-6)


def test_bisect_returns_midpoint_after_max_iterations() -> None:
    """A clearly non-bracketing pair shouldn't raise; the helper just
    returns the midpoint after exhausting iterations. Public callers
    bracket-check before invoking."""
    # f(x) = 1 has no root anywhere — sign never flips.
    result = _bisect(lambda x: 1.0, 0.0, 10.0, max_iter=10)
    assert math.isfinite(result)


def test_brent_finds_root_of_quadratic() -> None:
    root = _brent(lambda x: x * x - 2.0, 0.0, 2.0)
    assert root == pytest.approx(math.sqrt(2.0), abs=1e-9)


def test_brent_converges_in_fewer_iterations_than_bisection() -> None:
    """Brent's super-linear convergence should hit machine-precision
    on a smooth objective in < 20 iterations vs > 50 for bisection.
    We measure by counting fn evaluations."""
    bisect_calls = {"n": 0}
    brent_calls = {"n": 0}

    def f_bisect(x: float) -> float:
        bisect_calls["n"] += 1
        return x * x - 2.0

    def f_brent(x: float) -> float:
        brent_calls["n"] += 1
        return x * x - 2.0

    _bisect(f_bisect, 0.0, 2.0, tol=1e-12)
    _brent(f_brent, 0.0, 2.0, tol=1e-12)
    assert brent_calls["n"] < bisect_calls["n"]
    assert brent_calls["n"] < 30  # generous; typical is ~12


def test_brent_falls_back_to_bisection_on_non_bracketing_pair() -> None:
    """Defensive: a non-bracketing initial pair shouldn't raise.
    The fallback to ``_bisect`` keeps the contract identical to the
    pre-Brent behaviour."""
    # f(x) = x² + 1 is always positive; no root in any real bracket.
    result = _brent(lambda x: x * x + 1.0, 0.0, 5.0, max_iter=10)
    assert math.isfinite(result)


def test_brent_finds_root_of_decreasing_function() -> None:
    """Negative-slope objective — the sign convention inside Brent
    must follow the contrapoint correctly."""
    root = _brent(lambda x: 3.0 - x, 0.0, 10.0)
    assert root == pytest.approx(3.0, abs=1e-9)


def test_brent_respects_target_offset() -> None:
    """target=42 with f(x) = 7x − 14 gives root x = 8."""
    root = _brent(lambda x: 7.0 * x - 14.0, 0.0, 100.0, target=42.0)
    assert root == pytest.approx(8.0, abs=1e-9)


def test_brent_handles_already_at_root() -> None:
    """f(low) is exactly 0 — the loop should return immediately."""
    root = _brent(lambda x: x - 5.0, 5.0, 10.0)
    assert root == pytest.approx(5.0, abs=1e-12)


def test_brent_swaps_low_high_when_passed_reversed() -> None:
    root = _brent(lambda x: x - 7.0, 100.0, 0.0)
    assert root == pytest.approx(7.0, abs=1e-9)

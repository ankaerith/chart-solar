"""Private bisection solver shared by IRR and dealer-fee unmasking.

Both call sites do the same thing: walk a closed bracket on a
monotone-near-the-root function, narrowing until the residual is small
enough or the bracket collapses. This file factors that loop out so a
future Brent/Newton swap (chart-solar-nake) lands in one place.
"""

from __future__ import annotations

from collections.abc import Callable


def _bisect(
    fn: Callable[[float], float],
    low: float,
    high: float,
    *,
    target: float = 0.0,
    tol: float = 1e-9,
    bracket_tol: float = 1e-12,
    max_iter: int = 200,
) -> float:
    """Bracketed bisection on ``fn(x) - target``.

    Sign at the moving endpoint is tracked from the initial low-side
    evaluation, so the loop is correct for both increasing and
    decreasing objectives. Caller is responsible for ensuring the
    initial bracket actually straddles the root; this helper does not
    raise on a non-bracketing input — it just returns the midpoint
    after exhausting iterations.
    """
    if low > high:
        low, high = high, low
    f_low = fn(low) - target
    for _ in range(max_iter):
        mid = (low + high) / 2.0
        if (high - low) < bracket_tol:
            return mid
        f_mid = fn(mid) - target
        if abs(f_mid) < tol:
            return mid
        if f_mid * f_low > 0:
            low = mid
            f_low = f_mid
        else:
            high = mid
    return (low + high) / 2.0

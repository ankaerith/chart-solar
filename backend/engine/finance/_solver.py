"""Private bracketed root-finders for engine.finance.

Two solvers, both SciPy-free:

* ``_bisect`` — robust fallback, linear convergence. Used when we
  don't trust the function shape (rate vector with sign flips, dealer
  fee with cap-and-floor branches).
* ``_brent`` — Brent's method, super-linear convergence on smooth
  monotone-near-the-root functions. ~10–20 iterations vs ~200 for
  bisection at the same precision. IRR's NPV-vs-rate stream is
  monotone past the unique root for solar-shaped cashflows, so Brent
  is the right default there.

Both share the same call shape so a swap is a one-import change.
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


def _brent(
    fn: Callable[[float], float],
    low: float,
    high: float,
    *,
    target: float = 0.0,
    tol: float = 1e-9,
    bracket_tol: float = 1e-12,
    max_iter: int = 100,
) -> float:
    """Brent's method on ``fn(x) - target``.

    Combines bisection (robust) with inverse-quadratic interpolation
    and a secant step (fast). Falls back to bisection whenever the
    interpolated guess would be worse than the current bracket
    midpoint — that fallback is what makes Brent's worst case as good
    as bisection's while typically converging in ~12–20 iterations on
    smooth objectives.

    Caller must ensure ``fn(low) - target`` and ``fn(high) - target``
    bracket a root (their product is negative). Falls through to
    bisection-style midpoint return after ``max_iter`` if convergence
    stalls — same degraded-output behaviour as ``_bisect``.

    Reference: Brent, R.P. *Algorithms for Minimization Without
    Derivatives*, 1973, ch. 4.
    """
    if low > high:
        low, high = high, low

    f_a = fn(low) - target
    f_b = fn(high) - target
    if f_a * f_b > 0:
        # Caller passed a non-bracketing initial pair. Fall back to
        # bisection's degraded behaviour rather than raising — the
        # public IRR / dealer-fee functions check the bracket
        # explicitly before calling, so this branch is defensive.
        return _bisect(fn, low, high, target=target, tol=tol, bracket_tol=bracket_tol)

    # Brent's classic naming: a is the contrapoint, b the current
    # estimate (always carries the smaller |residual|), c the previous
    # contrapoint. d / e track the previous step lengths so we can
    # decide whether to accept an interpolated step.
    a, b = low, high
    if abs(f_a) < abs(f_b):
        a, b = b, a
        f_a, f_b = f_b, f_a
    c, f_c = a, f_a
    mflag = True
    d = 0.0  # only read when mflag is False

    for _ in range(max_iter):
        if abs(f_b) < tol:
            return b
        if abs(b - a) < bracket_tol:
            return b

        s: float
        if f_a != f_c and f_b != f_c:
            # Inverse-quadratic interpolation through (a, f_a),
            # (b, f_b), (c, f_c).
            s = (
                a * f_b * f_c / ((f_a - f_b) * (f_a - f_c))
                + b * f_a * f_c / ((f_b - f_a) * (f_b - f_c))
                + c * f_a * f_b / ((f_c - f_a) * (f_c - f_b))
            )
        else:
            # Secant step (linear interpolation).
            s = b - f_b * (b - a) / (f_b - f_a)

        # Brent's safety conditions: reject the interpolated guess
        # whenever it would land outside [(3a+b)/4, b] or fail to make
        # at least 50 % progress relative to the prior step.
        cond1 = not (((3 * a + b) / 4.0) < s < b or b < s < ((3 * a + b) / 4.0))
        cond2 = mflag and abs(s - b) >= abs(b - c) / 2.0
        cond3 = (not mflag) and abs(s - b) >= abs(c - d) / 2.0
        cond4 = mflag and abs(b - c) < bracket_tol
        cond5 = (not mflag) and abs(c - d) < bracket_tol
        if cond1 or cond2 or cond3 or cond4 or cond5:
            s = (a + b) / 2.0
            mflag = True
        else:
            mflag = False

        f_s = fn(s) - target
        d, c, f_c = c, b, f_b
        if f_a * f_s < 0:
            b, f_b = s, f_s
        else:
            a, f_a = s, f_s
        if abs(f_a) < abs(f_b):
            a, b = b, a
            f_a, f_b = f_b, f_a

    return b

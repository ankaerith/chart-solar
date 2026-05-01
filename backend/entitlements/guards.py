"""FastAPI dependency for tier gating + caller identity.

`require_feature("engine.tornado_chart")` returns a dependency that
raises HTTP 402 when the request's user tier is below the feature's
required tier. The user's tier comes from `current_tier` — a thin
indirection that Phase 2 will replace with the auth-bound user (and
that tests override via `app.dependency_overrides`).

`current_user_id` reads from ``request.state.user_id``, which the
session middleware stamps per request (chart-solar-ij9). When no
session cookie is present (or the cookie is invalid) the value
defaults to ``ANONYMOUS_USER_ID`` so existing call sites continue to
work as they did before auth landed.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from backend.entitlements.features import Tier, feature_required_tier, tier_satisfies


def current_tier() -> Tier:
    """Default user tier — overridable via `app.dependency_overrides`
    for tests, and replaced by the auth-bound user once Phase 2 ships."""
    return Tier.FREE


#: Stable identifier for the unauthenticated caller. Picked as a literal
#: string rather than ``None`` so storage lookups always have a
#: non-empty namespace key. The session middleware stamps the real
#: user id when a valid cookie is present; this is the fallback.
ANONYMOUS_USER_ID = "anonymous"


def current_user_id(request: Request) -> str:
    """Caller's user identifier, resolved via the session middleware.

    The middleware reads the session cookie, validates it against the
    ``sessions`` table, and stamps ``request.state.user_id``. Tests
    can either set the cookie (full-stack route exercise) or override
    this dep via ``app.dependency_overrides[current_user_id]`` to
    simulate distinct callers without going through magic-link auth.

    Returns ``ANONYMOUS_USER_ID`` when no cookie / invalid cookie —
    routes that require auth wrap this in
    :func:`backend.api.auth.require_authenticated`.
    """
    return getattr(request.state, "user_id", ANONYMOUS_USER_ID) or ANONYMOUS_USER_ID


def require_feature(feature_key: str) -> Callable[..., None]:
    """Return a FastAPI dependency that 402s if the caller's tier is too low.

    Validates `feature_key` against the registry at decoration time —
    typos fail loudly in tests rather than silently allowing access.
    """
    required = feature_required_tier(feature_key)

    def _guard(user_tier: Tier = Depends(current_tier)) -> None:
        if not tier_satisfies(user_tier, required):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "feature": feature_key,
                    "required_tier": required.value,
                    "current_tier": user_tier.value,
                },
            )

    return _guard

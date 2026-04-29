"""FastAPI dependency for tier gating.

`require_feature("engine.tornado_chart")` returns a dependency that
raises HTTP 402 when the request's user tier is below the feature's
required tier. The user's tier comes from `current_tier` — a thin
indirection that Phase 2 will replace with the auth-bound user (and
that tests override via `app.dependency_overrides`).
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from backend.entitlements.features import Tier, feature_required_tier, tier_satisfies


def current_tier() -> Tier:
    """Default user tier — overridable via `app.dependency_overrides`
    for tests, and replaced by the auth-bound user once Phase 2 ships."""
    return Tier.FREE


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

"""FastAPI dependency for tier gating."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from backend.entitlements.features import FEATURES, Tier


def _current_tier() -> Tier:
    # Phase 2 wires this to the authenticated user.
    return Tier.FREE


_TIER_RANK = {Tier.FREE: 0, Tier.DECISION_PACK: 1, Tier.TRACK: 2}


def _tier_satisfies(user: Tier, required: Tier) -> bool:
    return _TIER_RANK[user] >= _TIER_RANK[required]


def require_feature(feature_key: str) -> Callable[..., None]:
    required = FEATURES.get(feature_key)
    if required is None:
        raise RuntimeError(f"unknown feature key: {feature_key}")

    def _guard(user_tier: Tier = Depends(_current_tier)) -> None:
        if not _tier_satisfies(user_tier, required):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"feature requires tier {required.value}",
            )

    return _guard

"""Read-only entitlement endpoints.

`/api/entitlements/registry` returns the full feature → tier table so
the frontend `useEntitlement` hook can mirror it without duplicating
the registry. `/api/entitlements/me` returns the caller's effective
tier so the UI can render a tier badge / paywall preview.
"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.entitlements.features import FEATURES, Tier
from backend.entitlements.guards import current_tier

router = APIRouter()


@router.get("/entitlements/registry")
async def entitlement_registry() -> dict[str, Any]:
    """Public — the registry has no secret data, just the public price /
    tier mapping. Returned shape mirrors the frontend `useEntitlement`
    contract: `{features: {[key: string]: tier}, tiers: [tier]}`."""
    return {
        "features": {key: tier.value for key, tier in FEATURES.items()},
        "tiers": [t.value for t in Tier],
    }


@router.get("/entitlements/me")
async def entitlement_me(tier: Tier = Depends(current_tier)) -> dict[str, str]:
    """Effective tier for the current request. Phase 2 makes this
    auth-bound; today it returns the default until the auth layer lands."""
    return {"tier": tier.value}

"""Feature key registry: maps feature keys to product tiers.

Single source of truth for both the FastAPI guard (server-side) and the
frontend `useEntitlement` hook (client-side, mirrored via the
`/api/entitlements/registry` endpoint).

Promote / demote is a one-row change here — no migration, no code path
elsewhere needs to know about it.
"""

from enum import StrEnum


class Tier(StrEnum):
    """Customer tiers, ordered by access (free is the floor)."""

    FREE = "free"
    DECISION_PACK = "decision_pack"  # one-shot purchase, lifetime access to forecast features
    FOUNDERS = "founders"  # one-shot launch tier — same access as decision_pack
    TRACK = "track"  # subscription — adds ongoing monitoring


# Higher rank = more access. A user satisfies a feature requirement when
# their tier rank >= the feature's required tier rank.
TIER_RANK: dict[Tier, int] = {
    Tier.FREE: 0,
    Tier.DECISION_PACK: 1,
    Tier.FOUNDERS: 1,  # Founders == Decision Pack for access purposes
    Tier.TRACK: 2,
}


FEATURES: dict[str, Tier] = {
    # Phase 1a — engine
    "engine.basic_forecast": Tier.FREE,
    "engine.monte_carlo": Tier.FREE,
    "engine.npv_irr": Tier.FREE,
    "engine.tornado_chart": Tier.DECISION_PACK,
    # Phase 1b — audit / extraction
    "audit.proposal_extraction": Tier.DECISION_PACK,
    "audit.unlimited_runs": Tier.DECISION_PACK,
    # Phase 3 — battery + scenarios
    "engine.battery.hourly_dispatch": Tier.DECISION_PACK,
    "engine.scenario.diff": Tier.DECISION_PACK,
    # Phase 4 — Track (ongoing monitoring)
    "track.bill_variance": Tier.TRACK,
    "track.alerts": Tier.TRACK,
    "track.degradation_curve": Tier.TRACK,
}


def feature_required_tier(feature_key: str) -> Tier:
    """Look up the minimum tier required for `feature_key`.

    Raises `KeyError` for unknown keys — callers should treat this as a
    programmer error (registry is the source of truth)."""
    if feature_key not in FEATURES:
        raise KeyError(feature_key)
    return FEATURES[feature_key]


def tier_satisfies(user: Tier, required: Tier) -> bool:
    """Does the user's tier rank meet or exceed the required tier?"""
    return TIER_RANK[user] >= TIER_RANK[required]


def try_parse_tier(raw: str) -> Tier | None:
    """Coerce a raw string to a ``Tier``, returning ``None`` on miss."""
    try:
        return Tier(raw)
    except ValueError:
        return None

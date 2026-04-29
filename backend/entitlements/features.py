"""Feature key registry: maps feature keys to product tiers.

Single source of truth for both the FastAPI guard (server-side) and the
frontend `useEntitlement` hook (client-side, mirrored).
"""

from enum import StrEnum


class Tier(StrEnum):
    FREE = "free"
    DECISION_PACK = "decision_pack"
    TRACK = "track"


FEATURES: dict[str, Tier] = {
    # Phase 1a
    "engine.basic_forecast": Tier.FREE,
    # Phase 1b
    "audit.proposal_extraction": Tier.DECISION_PACK,
    # Phase 3
    "engine.battery.hourly_dispatch": Tier.DECISION_PACK,
    "engine.scenario.diff": Tier.DECISION_PACK,
    # Phase 4
    "track.bill_variance": Tier.TRACK,
}

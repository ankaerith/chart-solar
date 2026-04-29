import pytest
from fastapi import HTTPException

from backend.entitlements.features import FEATURES, Tier
from backend.entitlements.guards import _tier_satisfies, require_feature


def test_features_registered() -> None:
    assert FEATURES["engine.basic_forecast"] is Tier.FREE
    assert FEATURES["audit.proposal_extraction"] is Tier.DECISION_PACK
    assert FEATURES["track.bill_variance"] is Tier.TRACK


def test_tier_satisfies_monotonic() -> None:
    assert _tier_satisfies(Tier.DECISION_PACK, Tier.FREE)
    assert _tier_satisfies(Tier.TRACK, Tier.DECISION_PACK)
    assert not _tier_satisfies(Tier.FREE, Tier.DECISION_PACK)


def test_unknown_feature_key_raises() -> None:
    with pytest.raises(RuntimeError):
        require_feature("nope.does_not_exist")


def test_free_tier_blocked_from_decision_pack() -> None:
    guard = require_feature("audit.proposal_extraction")
    with pytest.raises(HTTPException) as exc:
        guard(user_tier=Tier.FREE)
    assert exc.value.status_code == 402

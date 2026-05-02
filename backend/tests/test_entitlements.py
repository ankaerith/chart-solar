"""Entitlement registry + FastAPI guard.

The unit half exercises the registry shape and tier-rank semantics.
The HTTP half wires `require_feature` into a real FastAPI route and
overrides `current_tier` per-request via `dependency_overrides` —
the same seam tests will keep using even though the default impl now
resolves the tier from the entitlements ledger.
"""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.entitlements.features import (
    FEATURES,
    TIER_RANK,
    Tier,
    feature_required_tier,
    tier_satisfies,
)
from backend.entitlements.guards import ANONYMOUS_USER_ID, current_tier, require_feature
from backend.main import app as production_app


def test_features_registered() -> None:
    assert FEATURES["engine.basic_forecast"] is Tier.FREE
    assert FEATURES["audit.proposal_extraction"] is Tier.DECISION_PACK
    assert FEATURES["track.bill_variance"] is Tier.TRACK


def test_promote_demote_is_one_row_change() -> None:
    """Sanity check that the registry IS one Python dict with one row
    per feature — promote/demote between tiers is a single edit."""
    assert isinstance(FEATURES, dict)
    for key, tier in FEATURES.items():
        assert isinstance(key, str)
        assert isinstance(tier, Tier)


def test_tier_satisfies_monotonic() -> None:
    assert tier_satisfies(Tier.DECISION_PACK, Tier.FREE)
    assert tier_satisfies(Tier.TRACK, Tier.DECISION_PACK)
    assert tier_satisfies(Tier.TRACK, Tier.FREE)
    assert not tier_satisfies(Tier.FREE, Tier.DECISION_PACK)
    assert not tier_satisfies(Tier.DECISION_PACK, Tier.TRACK)


def test_founders_satisfies_decision_pack_features() -> None:
    """Founders is a launch-tier alias for Decision Pack — same access."""
    assert tier_satisfies(Tier.FOUNDERS, Tier.DECISION_PACK)
    assert TIER_RANK[Tier.FOUNDERS] == TIER_RANK[Tier.DECISION_PACK]


def test_unknown_feature_key_raises_at_decoration() -> None:
    """Typos in feature keys should fail loudly, not silently allow access."""
    with pytest.raises(KeyError):
        feature_required_tier("nope.does_not_exist")
    with pytest.raises(KeyError):
        require_feature("nope.does_not_exist")


@pytest.fixture
def guarded_app() -> Iterator[tuple[FastAPI, dict[Tier, str]]]:
    """A tiny app with one route per tier sensitivity, used by every
    HTTP test below."""
    app = FastAPI()

    @app.get("/free", dependencies=[Depends(require_feature("engine.basic_forecast"))])
    async def free_route() -> dict[str, str]:
        return {"ok": "free"}

    @app.get(
        "/decision",
        dependencies=[Depends(require_feature("audit.proposal_extraction"))],
    )
    async def decision_route() -> dict[str, str]:
        return {"ok": "decision_pack"}

    @app.get("/track", dependencies=[Depends(require_feature("track.bill_variance"))])
    async def track_route() -> dict[str, str]:
        return {"ok": "track"}

    routes = {Tier.FREE: "/free", Tier.DECISION_PACK: "/decision", Tier.TRACK: "/track"}
    yield app, routes
    app.dependency_overrides.clear()


def _set_tier(app: FastAPI, tier: Tier) -> None:
    app.dependency_overrides[current_tier] = lambda: tier


def test_free_user_blocked_from_decision_pack(
    guarded_app: tuple[FastAPI, dict[Tier, str]],
) -> None:
    app, routes = guarded_app
    _set_tier(app, Tier.FREE)
    response = TestClient(app).get(routes[Tier.DECISION_PACK])
    assert response.status_code == 402
    body = response.json()["detail"]
    assert body["required_tier"] == Tier.DECISION_PACK.value
    assert body["current_tier"] == Tier.FREE.value


def test_decision_pack_user_can_hit_decision_pack_route(
    guarded_app: tuple[FastAPI, dict[Tier, str]],
) -> None:
    app, routes = guarded_app
    _set_tier(app, Tier.DECISION_PACK)
    response = TestClient(app).get(routes[Tier.DECISION_PACK])
    assert response.status_code == 200


def test_decision_pack_user_blocked_from_track(
    guarded_app: tuple[FastAPI, dict[Tier, str]],
) -> None:
    app, routes = guarded_app
    _set_tier(app, Tier.DECISION_PACK)
    response = TestClient(app).get(routes[Tier.TRACK])
    assert response.status_code == 402


def test_track_user_can_hit_every_route(
    guarded_app: tuple[FastAPI, dict[Tier, str]],
) -> None:
    app, routes = guarded_app
    _set_tier(app, Tier.TRACK)
    client = TestClient(app)
    for route in routes.values():
        assert client.get(route).status_code == 200


def test_founders_alias_can_hit_decision_pack_route(
    guarded_app: tuple[FastAPI, dict[Tier, str]],
) -> None:
    app, routes = guarded_app
    _set_tier(app, Tier.FOUNDERS)
    response = TestClient(app).get(routes[Tier.DECISION_PACK])
    assert response.status_code == 200


def _fake_request(user_id: str) -> Any:
    """Construct a Request stub good enough for current_tier()'s reads.

    The dep only touches ``request.state.user_id`` and writes
    ``request.state.tier``; nothing else on the Request is exercised
    in the path we test."""
    return SimpleNamespace(state=SimpleNamespace(user_id=user_id))


async def test_current_tier_short_circuits_anonymous_to_free() -> None:
    """Anonymous callers never hit the DB — the dep skips the SELECT."""
    request = _fake_request(ANONYMOUS_USER_ID)
    assert await current_tier(request) == Tier.FREE
    # Verify the result was memoised on request.state.
    assert request.state.tier == Tier.FREE


async def test_current_tier_reads_ledger_for_authenticated_user() -> None:
    """Authenticated callers query tier_for_user; we patch it to keep
    this unit-level (the integration path is exercised in
    test_stripe_webhook)."""
    request = _fake_request("a-real-user-id")
    with patch("backend.entitlements.guards.tier_for_user", return_value=Tier.TRACK):
        assert await current_tier(request) == Tier.TRACK
    assert request.state.tier == Tier.TRACK


async def test_current_tier_memoises_within_one_request() -> None:
    """Two calls inside the same request must share one DB roundtrip."""
    request = _fake_request("a-real-user-id")
    call_count = 0

    async def _stub(_session: object, _user_id: str) -> Tier:
        nonlocal call_count
        call_count += 1
        return Tier.DECISION_PACK

    with patch("backend.entitlements.guards.tier_for_user", side_effect=_stub):
        first = await current_tier(request)
        second = await current_tier(request)
    assert first == second == Tier.DECISION_PACK
    assert call_count == 1, "tier_for_user should be hit once per request"


def test_registry_endpoint_returns_full_table() -> None:
    response = TestClient(production_app).get("/api/entitlements/registry")
    assert response.status_code == 200
    body = response.json()
    assert set(body["features"].keys()) == set(FEATURES.keys())
    assert set(body["tiers"]) == {t.value for t in Tier}
    # Round-trip via Tier enum — tier values map back to the registry.
    for key, tier_value in body["features"].items():
        assert FEATURES[key].value == tier_value


def test_me_endpoint_reflects_overridden_tier() -> None:
    production_app.dependency_overrides[current_tier] = lambda: Tier.TRACK
    try:
        response = TestClient(production_app).get("/api/entitlements/me")
    finally:
        production_app.dependency_overrides.pop(current_tier, None)
    assert response.status_code == 200
    assert response.json() == {"tier": Tier.TRACK.value}

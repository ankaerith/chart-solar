"""End-to-end + unit tests for the Stripe webhook subscriber chain.

Three layers exercised:

* Pure routing (``route_event``) — no Stripe SDK, no DB.
* Webhook endpoint (``POST /api/stripe/webhook``) — TestClient,
  signed payloads, dedupe via the ``stripe_events`` table.
* Subscriber → ``user_entitlements`` ledger — async grant + revoke,
  idempotent on replay, ``tier_for_user`` reads back the correct tier,
  FK rejection on non-existent / unparseable user ids.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import backend.database as _db
from backend.db.auth_models import User
from backend.domain.events import PaymentRefunded, PaymentSucceeded
from backend.entitlements.features import Tier
from backend.infra.eventbus import clear_subscribers, dispatch_async
from backend.main import app
from backend.services.entitlements_grants import (
    grant_tier,
    revoke_by_event,
    tier_for_user,
)
from backend.services.entitlements_subscribers import register_subscribers
from backend.services.stripe_webhook_router import route_event

WEBHOOK_SECRET = "whsec_test_dummy_secret"  # noqa: S105 — test-only fixture


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_eventbus() -> Iterator[None]:
    """Strip subscribers before/after each test so registrations don't leak."""
    clear_subscribers()
    yield
    clear_subscribers()


@pytest.fixture(autouse=True)
def _stripe_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from backend.config import settings

    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET, raising=False)
    yield


@pytest.fixture
async def db_session() -> AsyncIterator[Any]:
    """A fresh AsyncSession against the test engine, with cleanup."""
    if _db.SessionLocal is None:
        pytest.skip("Postgres unavailable for integration tests")
    async with _db.SessionLocal() as session:
        yield session
        # FK on user_entitlements.user_id ON DELETE CASCADE means we
        # only need to drop users to clean both, but be explicit so a
        # failing test leaves the DB obviously empty for the next.
        await session.execute(text("DELETE FROM user_entitlements"))
        await session.execute(text("DELETE FROM stripe_events"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()


async def _make_user(session: Any, *, email: str | None = None) -> str:
    """Insert a User row and return its id as a string (the form Stripe
    metadata carries through the webhook router)."""
    suffix = uuid.uuid4().hex[:8]
    row = User(email=email or f"user-{suffix}@example.com")
    session.add(row)
    await session.commit()
    return str(row.id)


# ---------------------------------------------------------------------------
# Pure routing — no DB, no Stripe SDK
# ---------------------------------------------------------------------------


def _checkout_event(
    *,
    event_id: str = "evt_chk_1",
    user_id: str = "user_42",
    tier: str = "decision_pack",
    via: str = "client_reference_id",
) -> dict[str, Any]:
    obj: dict[str, Any] = {"object": "checkout.session", "metadata": {"tier": tier}}
    if via == "client_reference_id":
        obj["client_reference_id"] = user_id
    else:
        obj["metadata"]["user_id"] = user_id
    return {
        "id": event_id,
        "object": "event",
        "type": "checkout.session.completed",
        "data": {"object": obj},
    }


def _invoice_event(
    *,
    event_id: str = "evt_inv_1",
    user_id: str = "user_42",
    tier: str = "track",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "object": "event",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "object": "invoice",
                "metadata": {"user_id": user_id, "tier": tier},
            }
        },
    }


def _refund_event(
    *,
    event_id: str = "evt_ref_1",
    user_id: str = "user_42",
    tier: str = "decision_pack",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "object": "event",
        "type": "charge.refunded",
        "data": {
            "object": {
                "object": "charge",
                "metadata": {"user_id": user_id, "tier": tier},
            }
        },
    }


def test_route_checkout_session_via_client_reference_id_emits_payment_succeeded() -> None:
    event = route_event(_checkout_event(via="client_reference_id"))
    assert isinstance(event, PaymentSucceeded)
    assert event.user_id == "user_42"
    assert event.tier == "decision_pack"
    assert event.stripe_event_id == "evt_chk_1"


def test_route_checkout_session_falls_back_to_metadata_user_id() -> None:
    event = route_event(_checkout_event(via="metadata"))
    assert isinstance(event, PaymentSucceeded)
    assert event.user_id == "user_42"


def test_route_invoice_payment_succeeded_emits_payment_succeeded() -> None:
    event = route_event(_invoice_event())
    assert isinstance(event, PaymentSucceeded)
    assert event.tier == "track"


def test_route_charge_refunded_emits_payment_refunded() -> None:
    event = route_event(_refund_event())
    assert isinstance(event, PaymentRefunded)
    assert event.user_id == "user_42"
    assert event.tier == "decision_pack"


def test_route_unhandled_event_type_returns_none() -> None:
    assert (
        route_event(
            {"id": "x", "object": "event", "type": "customer.created", "data": {"object": {}}}
        )
        is None
    )


def test_route_handled_event_missing_metadata_returns_none() -> None:
    bad = _checkout_event()
    bad["data"]["object"]["client_reference_id"] = None
    bad["data"]["object"]["metadata"].pop("user_id", None)
    assert route_event(bad) is None


def test_route_unknown_tier_returns_none() -> None:
    bad = _checkout_event(tier="enterprise_god_mode")
    assert route_event(bad) is None


def test_route_malformed_event_returns_none() -> None:
    assert route_event({"data": {}}) is None


# ---------------------------------------------------------------------------
# DB grant / revoke / tier_for_user
# ---------------------------------------------------------------------------


async def test_grant_tier_inserts_and_replay_is_no_op(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    inserted_first = await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_1",
    )
    inserted_second = await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_1",
    )
    assert inserted_first is True
    assert inserted_second is False
    assert await tier_for_user(db_session, user_id) == Tier.DECISION_PACK


async def test_grant_tier_picks_highest_rank(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_dp",
    )
    await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.TRACK,
        granted_by_event_id="evt_tr",
    )
    assert await tier_for_user(db_session, user_id) == Tier.TRACK


async def test_grant_tier_rejects_unparseable_user_id(db_session: Any) -> None:
    """Stripe metadata cannot mint a tier for a string that is not a UUID."""
    inserted = await grant_tier(
        db_session,
        user_id="not-a-uuid",
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_invalid",
    )
    assert inserted is False
    # And no user_entitlement row was written.
    rows = (await db_session.execute(text("SELECT count(*) FROM user_entitlements"))).scalar_one()
    assert rows == 0


async def test_grant_tier_rejects_unknown_user(db_session: Any) -> None:
    """A well-formed UUID that does not exist in users is rejected by the FK."""
    fabricated = str(uuid.uuid4())
    inserted = await grant_tier(
        db_session,
        user_id=fabricated,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_phantom",
    )
    assert inserted is False
    rows = (await db_session.execute(text("SELECT count(*) FROM user_entitlements"))).scalar_one()
    assert rows == 0


async def test_revoke_marks_active_grant(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_g",
    )
    revoked = await revoke_by_event(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        revoked_by_event_id="evt_r",
    )
    assert revoked is True
    assert await tier_for_user(db_session, user_id) == Tier.FREE


async def test_revoke_replay_is_no_op(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_g2",
    )
    first = await revoke_by_event(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        revoked_by_event_id="evt_r2",
    )
    # Re-deliver the same refund event — must not raise + must not flip
    # an unrelated grant.
    await grant_tier(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        granted_by_event_id="evt_g3",
    )
    second = await revoke_by_event(
        db_session,
        user_id=user_id,
        tier=Tier.DECISION_PACK,
        revoked_by_event_id="evt_r2",
    )
    assert first is True
    assert second is False
    # The newer grant remains untouched.
    assert await tier_for_user(db_session, user_id) == Tier.DECISION_PACK


async def test_tier_for_user_anonymous_returns_free(db_session: Any) -> None:
    """The string ``anonymous`` is the unauthenticated sentinel — it does
    not parse as a UUID, so tier resolution short-circuits to FREE."""
    assert await tier_for_user(db_session, "anonymous") == Tier.FREE


async def test_tier_for_user_with_no_rows_returns_free(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    assert await tier_for_user(db_session, user_id) == Tier.FREE


# ---------------------------------------------------------------------------
# Subscriber via the in-process bus
# ---------------------------------------------------------------------------


async def test_subscriber_grants_tier_on_payment_succeeded(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    register_subscribers()
    await dispatch_async(
        PaymentSucceeded(
            user_id=user_id,
            tier=Tier.DECISION_PACK,
            stripe_event_id="evt_e1",
        )
    )
    assert await tier_for_user(db_session, user_id) == Tier.DECISION_PACK


async def test_subscriber_revokes_tier_on_payment_refunded(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    register_subscribers()
    await dispatch_async(
        PaymentSucceeded(
            user_id=user_id,
            tier=Tier.DECISION_PACK,
            stripe_event_id="evt_f1",
        )
    )
    await dispatch_async(
        PaymentRefunded(
            user_id=user_id,
            tier=Tier.DECISION_PACK,
            stripe_event_id="evt_f2",
        )
    )
    assert await tier_for_user(db_session, user_id) == Tier.FREE


# ---------------------------------------------------------------------------
# End-to-end via the FastAPI endpoint
# ---------------------------------------------------------------------------


def _sign(payload: bytes, *, secret: str = WEBHOOK_SECRET, ts: int | None = None) -> str:
    timestamp = ts if ts is not None else int(time.time())
    signed = f"{timestamp}.{payload.decode()}"
    sig = hmac.new(
        secret.encode("utf-8"),
        msg=signed.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={sig}"


def test_webhook_rejects_invalid_signature() -> None:
    register_subscribers()
    payload = json.dumps(_checkout_event(event_id="evt_bad", user_id="user_g")).encode()
    with TestClient(app) as client:
        resp = client.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"Stripe-Signature": "t=1,v1=deadbeef"},
        )
    assert resp.status_code == 400


async def test_webhook_grants_tier_on_checkout_session_completed(db_session: Any) -> None:
    user_id = await _make_user(db_session)
    register_subscribers()
    payload = json.dumps(_checkout_event(event_id="evt_h1", user_id=user_id)).encode()
    sig = _sign(payload)
    with TestClient(app) as client:
        resp = client.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"Stripe-Signature": sig},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "event_id": "evt_h1"}

    # The subscriber ran inside the request, so the entitlement is
    # visible synchronously after the response. Re-open the session
    # because db_session was used above; SQLAlchemy AsyncSession
    # caching means a fresh session reads the committed write.
    async with _db.SessionLocal() as s:
        assert await tier_for_user(s, user_id) == Tier.DECISION_PACK


async def test_webhook_rejects_grant_for_unknown_user(db_session: Any) -> None:
    """A signed-but-bogus user_id must not grant a tier — the FK rejects
    the insert, the subscriber returns False, the webhook still 200s."""
    fabricated_user = str(uuid.uuid4())
    register_subscribers()
    payload = json.dumps(_checkout_event(event_id="evt_phantom", user_id=fabricated_user)).encode()
    sig = _sign(payload)
    with TestClient(app) as client:
        resp = client.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"Stripe-Signature": sig},
        )
    # Webhook returns ok (Stripe must not retry) but no entitlement was created.
    assert resp.status_code == 200
    async with _db.SessionLocal() as s:
        assert await tier_for_user(s, fabricated_user) == Tier.FREE


def test_webhook_replay_is_acknowledged_without_re_dispatch(db_session: Any) -> None:
    register_subscribers()
    # Use a plausible user_id here; even if it does not exist, the dedupe
    # behaviour we are asserting (replay → "replay" status) is independent
    # of grant success.
    fabricated_user = str(uuid.uuid4())
    payload = json.dumps(_checkout_event(event_id="evt_i1", user_id=fabricated_user)).encode()
    sig = _sign(payload)
    with TestClient(app) as client:
        first = client.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"Stripe-Signature": sig},
        )
        second = client.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"Stripe-Signature": _sign(payload)},
        )
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json() == {"status": "replay", "event_id": "evt_i1"}


def test_webhook_ignored_event_type_returns_status_ignored() -> None:
    register_subscribers()
    payload = json.dumps(
        {
            "id": "evt_j",
            "object": "event",
            "type": "customer.created",
            "data": {"object": {}},
        }
    ).encode()
    sig = _sign(payload)
    with TestClient(app) as client:
        resp = client.post(
            "/api/stripe/webhook",
            content=payload,
            headers={"Stripe-Signature": sig},
        )
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ignored",
        "event_id": "evt_j",
        "event_type": "customer.created",
    }

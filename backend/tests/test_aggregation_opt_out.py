"""Per-user aggregation opt-out (ADR 0005, chart-solar-fc1).

Covers the schema invariant (default-on for new audits and users), the
service-layer cascade, and the route-level contract: anonymous callers
hit 401, idempotency holds across re-calls, and re-flipping back to
opted-in does NOT auto-resume historical audits.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

import backend.database as _db
from backend.db.audit_models import Audit, Installer, InstallerQuote
from backend.db.auth_models import User
from backend.entitlements.guards import current_user_id
from backend.main import app
from backend.services.audit_service import set_user_aggregation_opt_out

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


@pytest.fixture
def client_alice() -> Iterator[TestClient]:
    app.dependency_overrides[current_user_id] = lambda: str(ALICE)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(current_user_id, None)


@pytest.fixture
def client_anonymous() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def db() -> AsyncIterator[Any]:
    if _db.SessionLocal is None:
        pytest.skip("Postgres unavailable for integration tests")
    async with _db.SessionLocal() as session:
        yield session
        await session.execute(text("DELETE FROM installer_quotes"))
        await session.execute(text("DELETE FROM audits"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()


async def _make_user(session: Any, *, user_id: uuid.UUID, email: str) -> None:
    """Insert a User row with default aggregation_opt_out=False."""
    session.add(User(id=user_id, email=email))
    await session.commit()


async def _make_audit_with_quote(
    session: Any,
    *,
    owner: uuid.UUID,
    aggregation_opt_in: bool = True,
) -> tuple[uuid.UUID, uuid.UUID]:
    audit = Audit(user_id=owner, location_bucket="98101")
    session.add(audit)
    await session.commit()

    installer = Installer(canonical_name=f"Installer-{uuid.uuid4()}")
    session.add(installer)
    await session.commit()

    quote = InstallerQuote(
        audit_id=audit.id,
        installer_id=installer.id,
        aggregation_opt_in=aggregation_opt_in,
    )
    session.add(quote)
    await session.commit()
    return audit.id, quote.id


# ---------------------------------------------------------------------------
# Schema defaults — verifies ADR 0005's "default ON" invariant
# ---------------------------------------------------------------------------


async def test_new_user_defaults_to_aggregation_opted_in(db: Any) -> None:
    """``users.aggregation_opt_out`` defaults FALSE — the user is in by
    default, the column is the *override* not the consent."""
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    async with _db.SessionLocal() as session:
        row = await session.scalar(select(User).where(User.id == ALICE))
        assert row is not None
        assert row.aggregation_opt_out is False


async def test_new_quote_defaults_to_aggregation_opted_in(db: Any) -> None:
    """``installer_quotes.aggregation_opt_in`` defaults TRUE."""
    _, quote_id = await _make_audit_with_quote(db, owner=ALICE)
    async with _db.SessionLocal() as session:
        quote = await session.get(InstallerQuote, quote_id)
        assert quote is not None
        assert quote.aggregation_opt_in is True


# ---------------------------------------------------------------------------
# Service-layer cascade
# ---------------------------------------------------------------------------


async def test_opt_out_flips_user_flag_and_cascades_to_quotes(db: Any) -> None:
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    audit_id, quote_id = await _make_audit_with_quote(db, owner=ALICE)

    async with _db.SessionLocal() as session:
        result = await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=True)
    assert result == {"opt_out": True, "cascaded_rows": 1}

    async with _db.SessionLocal() as session:
        user = await session.get(User, ALICE)
        assert user is not None
        assert user.aggregation_opt_out is True
        quote = await session.get(InstallerQuote, quote_id)
        assert quote is not None
        assert quote.aggregation_opt_in is False
        # Audit row itself is untouched.
        assert await session.get(Audit, audit_id) is not None


async def test_opt_out_cascade_only_touches_callers_quotes(db: Any) -> None:
    """Bob's quote must not flip when Alice opts out."""
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    await _make_user(db, user_id=BOB, email="bob@example.com")
    _, alice_quote = await _make_audit_with_quote(db, owner=ALICE)
    _, bob_quote = await _make_audit_with_quote(db, owner=BOB)

    async with _db.SessionLocal() as session:
        await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=True)

    async with _db.SessionLocal() as session:
        alice = await session.get(InstallerQuote, alice_quote)
        bob = await session.get(InstallerQuote, bob_quote)
        assert alice is not None
        assert bob is not None
        assert alice.aggregation_opt_in is False
        assert bob.aggregation_opt_in is True


async def test_re_flipping_to_opted_in_does_not_resume_historical_audits(
    db: Any,
) -> None:
    """ADR 0005: opt-in flip-back affects future audits only."""
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    _, quote_id = await _make_audit_with_quote(db, owner=ALICE)

    async with _db.SessionLocal() as session:
        await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=True)
    async with _db.SessionLocal() as session:
        result = await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=False)
    assert result == {"opt_out": False, "cascaded_rows": 0}

    async with _db.SessionLocal() as session:
        user = await session.get(User, ALICE)
        assert user is not None
        assert user.aggregation_opt_out is False
        # Quote stays opted-out — historical audit NOT auto-resumed.
        quote = await session.get(InstallerQuote, quote_id)
        assert quote is not None
        assert quote.aggregation_opt_in is False


async def test_opt_out_is_idempotent(db: Any) -> None:
    """Setting the same value twice is a no-op on the second call."""
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    await _make_audit_with_quote(db, owner=ALICE)

    async with _db.SessionLocal() as session:
        first = await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=True)
    async with _db.SessionLocal() as session:
        second = await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=True)
    assert first == {"opt_out": True, "cascaded_rows": 1}
    assert second == {"opt_out": True, "cascaded_rows": 0}


async def test_new_audit_after_opt_out_still_writes_default_on(db: Any) -> None:
    """The user's flag is per-user; the column DEFAULT TRUE on
    ``installer_quotes`` is intentionally not aware of it. New audits
    after opt-out still write opted-in rows; the *next* aggregate pass
    is what excludes the user (via the user flag). This pins ADR
    0005's "re-flipping doesn't auto-resume historical, but new audits
    write aggregation_opt_in=true again" semantic."""
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    async with _db.SessionLocal() as session:
        await set_user_aggregation_opt_out(session, user_id=str(ALICE), opt_out=True)

    _, new_quote = await _make_audit_with_quote(db, owner=ALICE)
    async with _db.SessionLocal() as session:
        quote = await session.get(InstallerQuote, new_quote)
        assert quote is not None
        assert quote.aggregation_opt_in is True


# ---------------------------------------------------------------------------
# API route
# ---------------------------------------------------------------------------


def test_patch_aggregation_returns_401_for_anonymous(
    client_anonymous: TestClient,
) -> None:
    resp = client_anonymous.patch("/api/me/aggregation", json={"opt_out": True})
    assert resp.status_code == 401


async def test_patch_aggregation_flips_and_cascades_via_route(
    db: Any,
    client_alice: TestClient,
) -> None:
    await _make_user(db, user_id=ALICE, email="alice@example.com")
    _, quote_id = await _make_audit_with_quote(db, owner=ALICE)

    resp = client_alice.patch("/api/me/aggregation", json={"opt_out": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["opt_out"] is True
    assert body["cascaded_rows"] == 1

    async with _db.SessionLocal() as session:
        user = await session.get(User, ALICE)
        assert user is not None
        assert user.aggregation_opt_out is True
        quote = await session.get(InstallerQuote, quote_id)
        assert quote is not None
        assert quote.aggregation_opt_in is False


def test_patch_aggregation_rejects_missing_field(client_alice: TestClient) -> None:
    """Pydantic body validator should reject a payload missing ``opt_out``."""
    resp = client_alice.patch("/api/me/aggregation", json={})
    assert resp.status_code == 422

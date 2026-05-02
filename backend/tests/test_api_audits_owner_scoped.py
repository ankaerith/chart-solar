"""Owner-scoped read + delete on /api/audits/{id} and /api/me/pii.

Covers chart-solar-kqkr (row-level access) and chart-solar-5c6 (audit
+ PII vault deletion). The fixtures simulate distinct callers via
``app.dependency_overrides[current_user_id]`` — magic-link auth lands
in chart-solar-ij9 and will replace the override with a JWT subject;
the test discipline here doesn't change.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

import backend.database as _db
from backend.db.audit_models import Audit, InstallerQuote, UserPiiVault
from backend.tests.conftest import ALICE_USER_ID, BOB_USER_ID, make_audit

ALICE = ALICE_USER_ID
BOB = BOB_USER_ID


async def _make_installer(session: Any) -> uuid.UUID:
    from backend.db.audit_models import Installer

    installer = Installer(canonical_name="Test Installer Co")
    session.add(installer)
    await session.commit()
    return installer.id


# ---------------------------------------------------------------------------
# Anonymous access — must 401
# ---------------------------------------------------------------------------


def test_get_audit_returns_401_for_anonymous_caller(
    client_anonymous: TestClient,
) -> None:
    resp = client_anonymous.get(f"/api/audits/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_delete_audit_returns_401_for_anonymous_caller(
    client_anonymous: TestClient,
) -> None:
    resp = client_anonymous.delete(f"/api/audits/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_delete_pii_returns_401_for_anonymous_caller(
    client_anonymous: TestClient,
) -> None:
    resp = client_anonymous.delete("/api/me/pii")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Row-level access — wrong owner collapses to 404
# ---------------------------------------------------------------------------


async def test_get_audit_returns_404_when_caller_is_not_the_owner(
    db: Any,
    client_bob: TestClient,
) -> None:
    audit_id = await make_audit(db, owner=ALICE)
    resp = client_bob.get(f"/api/audits/{audit_id}")
    # 404 *not* 403 — prevents enumeration (chart-solar-kqkr 3).
    assert resp.status_code == 404


async def test_delete_audit_returns_404_when_caller_is_not_the_owner(
    db: Any,
    client_bob: TestClient,
) -> None:
    audit_id = await make_audit(db, owner=ALICE)
    resp = client_bob.delete(f"/api/audits/{audit_id}")
    assert resp.status_code == 404
    # The audit row must still exist after Bob's failed delete.
    async with _db.SessionLocal() as session:
        survivor = await session.get(Audit, audit_id)
        assert survivor is not None


async def test_get_audit_returns_404_for_unknown_id(client_alice: TestClient) -> None:
    resp = client_alice.get(f"/api/audits/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Owner-scoped read + delete happy paths
# ---------------------------------------------------------------------------


async def test_owner_reads_their_own_audit(
    db: Any,
    client_alice: TestClient,
) -> None:
    audit_id = await make_audit(db, owner=ALICE)
    resp = client_alice.get(f"/api/audits/{audit_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(audit_id)
    assert body["location_bucket"] == "98101"


async def test_owner_deletes_their_own_audit_and_quotes_cascade(
    db: Any,
    client_alice: TestClient,
) -> None:
    audit_id = await make_audit(db, owner=ALICE)
    installer_id = await _make_installer(db)
    quote = InstallerQuote(audit_id=audit_id, installer_id=installer_id)
    db.add(quote)
    await db.commit()
    quote_id = quote.id

    resp = client_alice.delete(f"/api/audits/{audit_id}")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "audit_id": str(audit_id)}

    async with _db.SessionLocal() as session:
        assert await session.get(Audit, audit_id) is None
        # FK ondelete=CASCADE on installer_quotes.audit_id pulls the
        # quote with it.
        assert await session.get(InstallerQuote, quote_id) is None


async def test_delete_audit_replay_returns_404(
    db: Any,
    client_alice: TestClient,
) -> None:
    audit_id = await make_audit(db, owner=ALICE)
    first = client_alice.delete(f"/api/audits/{audit_id}")
    second = client_alice.delete(f"/api/audits/{audit_id}")
    assert first.status_code == 200
    # Already gone — 404 (the route layer never sees the row).
    assert second.status_code == 404


# ---------------------------------------------------------------------------
# PII vault deletion
# ---------------------------------------------------------------------------


async def test_delete_pii_drops_vault_rows_and_audit_link_becomes_null(
    db: Any,
    client_alice: TestClient,
) -> None:
    vault = UserPiiVault(
        user_id=ALICE,
        full_name="Alice Anderson",
        email="alice@example.com",
    )
    db.add(vault)
    await db.commit()
    vault_id = vault.id

    audit = Audit(user_id=ALICE, user_pii_vault_id=vault_id)
    db.add(audit)
    await db.commit()
    audit_id = audit.id

    resp = client_alice.delete("/api/me/pii")
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "rows": 1}

    async with _db.SessionLocal() as session:
        assert await session.get(UserPiiVault, vault_id) is None
        # The audit survives, with its link to the vault nulled out
        # (FK SET NULL on audits.user_pii_vault_id).
        survivor = await session.get(Audit, audit_id)
        assert survivor is not None
        assert survivor.user_pii_vault_id is None


async def test_delete_pii_replay_is_idempotent(
    db: Any,
    client_alice: TestClient,
) -> None:
    vault = UserPiiVault(user_id=ALICE, email="alice@example.com")
    db.add(vault)
    await db.commit()

    first = client_alice.delete("/api/me/pii")
    second = client_alice.delete("/api/me/pii")
    assert first.json() == {"status": "deleted", "rows": 1}
    assert second.json() == {"status": "deleted", "rows": 0}


async def test_delete_pii_only_drops_callers_rows(
    db: Any,
    client_alice: TestClient,
) -> None:
    db.add(UserPiiVault(user_id=ALICE, email="alice@example.com"))
    db.add(UserPiiVault(user_id=BOB, email="bob@example.com"))
    await db.commit()

    resp = client_alice.delete("/api/me/pii")
    assert resp.json() == {"status": "deleted", "rows": 1}

    async with _db.SessionLocal() as session:
        from sqlalchemy import select

        bobs_rows = (
            (await session.execute(select(UserPiiVault).where(UserPiiVault.user_id == BOB)))
            .scalars()
            .all()
        )
        assert len(bobs_rows) == 1


# ---------------------------------------------------------------------------
# Direct service-layer round-trip (no HTTP)
# ---------------------------------------------------------------------------


async def test_find_audit_owned_by_filters_by_user_id(db: Any) -> None:
    from backend.services.audit_service import find_audit_owned_by

    alice_audit_id = await make_audit(db, owner=ALICE)
    await make_audit(db, owner=BOB)

    found = await find_audit_owned_by(db, audit_id=alice_audit_id, user_id=str(ALICE))
    assert found is not None
    assert found.id == alice_audit_id

    misowned = await find_audit_owned_by(db, audit_id=alice_audit_id, user_id=str(BOB))
    assert misowned is None

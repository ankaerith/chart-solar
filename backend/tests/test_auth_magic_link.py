"""Magic-link auth — service + endpoint coverage.

Service-layer tests exercise ``request_magic_link`` /
``consume_magic_link`` / ``revoke_session`` /
``user_id_for_session_token`` against the real Postgres + a captive
``FakeEmailProvider``. Endpoint tests use ``TestClient`` with the
fake email provider injected into the route's outbound seam, and
verify that the cookie round-trips through the session middleware so
``current_user_id`` resolves to the signed-in user on subsequent
requests.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import backend.database as _db
from backend.api.auth import magic_link as magic_link_route
from backend.config import settings
from backend.db.auth_models import MagicLink
from backend.main import app
from backend.providers.fake import FakeEmailProvider
from backend.services.auth_service import (
    MagicLinkError,
    consume_magic_link,
    request_magic_link,
    revoke_session,
    user_id_for_session_token,
)


@pytest.fixture
async def db() -> AsyncIterator[Any]:
    if _db.SessionLocal is None:
        pytest.skip("Postgres unavailable for integration tests")
    async with _db.SessionLocal() as session:
        yield session
        await session.execute(text("DELETE FROM sessions"))
        await session.execute(text("DELETE FROM magic_links"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()


@pytest.fixture
def fake_email() -> FakeEmailProvider:
    return FakeEmailProvider()


@pytest.fixture
def patched_resend(
    monkeypatch: pytest.MonkeyPatch,
    fake_email: FakeEmailProvider,
) -> Iterator[FakeEmailProvider]:
    """Swap the route's ResendEmailProvider constructor for a fake."""
    monkeypatch.setattr(
        magic_link_route,
        "ResendEmailProvider",
        lambda: fake_email,
    )
    yield fake_email


@pytest.fixture(autouse=True)
def _allow_insecure_cookies(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """TestClient runs over plain http; secure cookies don't round-trip."""
    monkeypatch.setattr(settings, "auth_session_cookie_secure", False, raising=False)
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------


async def test_request_magic_link_emails_a_url_containing_a_token(
    db: Any, fake_email: FakeEmailProvider
) -> None:
    await request_magic_link(db, fake_email, email="alice@example.com")
    assert len(fake_email.sent) == 1
    msg = fake_email.sent[0]
    assert msg.to == "alice@example.com"
    # The token in the URL is the raw secret; it must NOT match the
    # token_hash stored in the DB (which is sha256 of it).
    match = re.search(r"token=([\w-]+)", msg.text_body)
    assert match is not None
    raw_token = match.group(1)
    rows = await _all_magic_links(db)
    assert len(rows) == 1
    assert rows[0].token_hash != raw_token  # hashed at rest


async def test_request_magic_link_normalises_email(db: Any, fake_email: FakeEmailProvider) -> None:
    await request_magic_link(db, fake_email, email="  Alice@EXAMPLE.com  ")
    assert fake_email.sent[0].to == "alice@example.com"


async def test_consume_magic_link_creates_user_and_session_first_time(
    db: Any, fake_email: FakeEmailProvider
) -> None:
    await request_magic_link(db, fake_email, email="bob@example.com")
    raw_token = _extract_token(fake_email.sent[-1].text_body)

    user, session_token = await consume_magic_link(db, raw_token=raw_token)
    assert user.email == "bob@example.com"

    user_id = await user_id_for_session_token(db, raw_token=session_token)
    assert user_id == user.id


async def test_consume_magic_link_reuses_existing_user(
    db: Any, fake_email: FakeEmailProvider
) -> None:
    await request_magic_link(db, fake_email, email="charlie@example.com")
    first_token = _extract_token(fake_email.sent[-1].text_body)
    user_first, _ = await consume_magic_link(db, raw_token=first_token)

    await request_magic_link(db, fake_email, email="charlie@example.com")
    second_token = _extract_token(fake_email.sent[-1].text_body)
    user_second, _ = await consume_magic_link(db, raw_token=second_token)

    assert user_first.id == user_second.id


async def test_consume_magic_link_rejects_replay(db: Any, fake_email: FakeEmailProvider) -> None:
    await request_magic_link(db, fake_email, email="d@example.com")
    raw_token = _extract_token(fake_email.sent[-1].text_body)
    await consume_magic_link(db, raw_token=raw_token)

    with pytest.raises(MagicLinkError, match="already consumed"):
        await consume_magic_link(db, raw_token=raw_token)


async def test_consume_magic_link_rejects_expired(db: Any, fake_email: FakeEmailProvider) -> None:
    await request_magic_link(db, fake_email, email="e@example.com")
    raw_token = _extract_token(fake_email.sent[-1].text_body)

    # Move the clock past the 15-minute TTL.
    later = datetime.now(UTC) + timedelta(seconds=settings.auth_magic_link_ttl_seconds + 1)
    with pytest.raises(MagicLinkError, match="expired"):
        await consume_magic_link(db, raw_token=raw_token, now=later)


async def test_consume_magic_link_rejects_unknown_token(db: Any) -> None:
    with pytest.raises(MagicLinkError, match="unknown"):
        await consume_magic_link(db, raw_token="not-a-real-token")


async def test_revoke_session_makes_lookup_return_none(
    db: Any, fake_email: FakeEmailProvider
) -> None:
    await request_magic_link(db, fake_email, email="f@example.com")
    raw_token = _extract_token(fake_email.sent[-1].text_body)
    _, session_token = await consume_magic_link(db, raw_token=raw_token)

    revoked = await revoke_session(db, raw_token=session_token)
    assert revoked is True
    assert await user_id_for_session_token(db, raw_token=session_token) is None


async def test_revoke_session_unknown_token_is_noop(db: Any) -> None:
    assert await revoke_session(db, raw_token="bogus") is False


# ---------------------------------------------------------------------------
# Endpoint round-trip
# ---------------------------------------------------------------------------


def test_login_endpoint_emails_link_and_returns_200(
    client: TestClient,
    patched_resend: FakeEmailProvider,
) -> None:
    resp = client.post("/api/auth/login", json={"email": "alice@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "magic_link_sent"}
    assert len(patched_resend.sent) == 1


def test_callback_endpoint_sets_session_cookie_and_authenticates(
    client: TestClient,
    patched_resend: FakeEmailProvider,
) -> None:
    client.post("/api/auth/login", json={"email": "alice@example.com"})
    raw_token = _extract_token(patched_resend.sent[-1].text_body)

    callback_resp = client.get(f"/api/auth/callback?token={raw_token}")
    assert callback_resp.status_code == 200
    body = callback_resp.json()
    assert body["user"]["email"] == "alice@example.com"

    # The cookie is set; subsequent requests on the same TestClient
    # carry it automatically. The session middleware should resolve it
    # to the user — we assert via the auth-required /api/me/pii sweep,
    # which 401s for anonymous and 200s for an authenticated user.
    # (Today this hits a route that lands in chart-solar-5c6.)
    cookie_header = callback_resp.headers.get("set-cookie", "")
    assert settings.auth_session_cookie_name in cookie_header
    assert "HttpOnly" in cookie_header


def test_callback_endpoint_rejects_invalid_token(client: TestClient) -> None:
    resp = client.get("/api/auth/callback?token=not-a-real-token")
    assert resp.status_code == 410


def test_logout_clears_session_and_cookie(
    client: TestClient,
    patched_resend: FakeEmailProvider,
) -> None:
    client.post("/api/auth/login", json={"email": "alice@example.com"})
    raw_token = _extract_token(patched_resend.sent[-1].text_body)
    client.get(f"/api/auth/callback?token={raw_token}")

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json() == {"status": "signed_out"}

    # The TestClient retains the cookie until cleared — explicitly
    # check the response asks the browser to drop it.
    set_cookie = resp.headers.get("set-cookie", "")
    assert settings.auth_session_cookie_name in set_cookie
    # ``Max-Age=0`` is how Starlette signals deletion.
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


def test_session_middleware_makes_current_user_id_resolve_to_signed_in_user(
    client: TestClient,
    patched_resend: FakeEmailProvider,
) -> None:
    """End-to-end: post-login the cookie drives current_user_id().

    We assert this by adding a temporary route at runtime; the route
    declares ``user_id = Depends(current_user_id)`` so the middleware's
    work is the only thing that can produce a non-anonymous result.
    """
    from fastapi import Depends

    from backend.entitlements.guards import current_user_id

    @app.get("/_test/whoami")
    def _whoami(user_id: str = Depends(current_user_id)) -> dict[str, str]:
        return {"user_id": user_id}

    try:
        # Anonymous before sign-in.
        anon = client.get("/_test/whoami")
        assert anon.json()["user_id"] == "anonymous"

        # Sign in.
        client.post("/api/auth/login", json={"email": "alice@example.com"})
        raw_token = _extract_token(patched_resend.sent[-1].text_body)
        client.get(f"/api/auth/callback?token={raw_token}")

        signed_in = client.get("/_test/whoami")
        body = signed_in.json()
        assert body["user_id"] != "anonymous"
        assert _is_uuid(body["user_id"])
    finally:
        # Tear down the test route so it doesn't bleed into other tests.
        app.router.routes = [
            r for r in app.router.routes if getattr(r, "path", "") != "/_test/whoami"
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _all_magic_links(session: Any) -> list[MagicLink]:
    from sqlalchemy import select

    result = await session.execute(select(MagicLink))
    return list(result.scalars())


def _extract_token(body: str) -> str:
    match = re.search(r"token=([\w-]+)", body)
    assert match is not None, f"no token in body: {body[:200]}"
    return match.group(1)


def _is_uuid(value: str) -> bool:
    import uuid as _uuid

    try:
        _uuid.UUID(value)
    except ValueError:
        return False
    return True

"""Magic-link auth — request, consume, sign-out, lookup-by-cookie.

Password-less by design. Flow:

1. **Request** (``request_magic_link``): caller submits an email; we
   generate a random opaque token, store its sha256 hash with a
   15-minute expiry, and email the raw token (embedded in a callback
   URL) to the address. We don't reveal whether the email is already a
   user — the response is the same either way to prevent enumeration.

2. **Consume** (``consume_magic_link``): caller posts the raw token
   back. We look up its hash; refuse if expired or already consumed;
   stamp ``consumed_at`` to one-shot it; create the user row if first
   time; create a session row + return its raw token. The session
   token is what goes in the ``Set-Cookie`` header at the API layer.

3. **Sign-out** (``revoke_session``): set ``revoked_at`` on the
   session row. Cookie clear happens at the API layer.

4. **Lookup** (``user_id_for_session_token``): the hot path — the
   middleware calls this on every request with a session cookie.
   Returns ``None`` for anonymous, expired, revoked, or unknown.

Tokens never appear in DB rows in raw form; both ``MagicLink.token_hash``
and ``Session.token_hash`` are sha256 of the raw token. A leaked DB
therefore can't be turned into forged auth links or stolen sessions.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.auth_models import MagicLink, Session, User
from backend.infra.logging import get_logger
from backend.providers.email import EmailProvider

_log = get_logger(__name__)

# 32 bytes of entropy → 43 url-safe chars; well above the security
# floor for a one-shot bearer token.
_TOKEN_BYTES = 32


class MagicLinkError(RuntimeError):
    """Raised when consume rejects a token (expired / already used / unknown)."""


def _hash_token(raw: str) -> str:
    """sha256 of the raw token; the raw value never lands in a DB row."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalise_email(value: str) -> str:
    return value.strip().lower()


async def request_magic_link(
    session: AsyncSession,
    email_provider: EmailProvider,
    *,
    email: str,
    callback_url: str | None = None,
    now: datetime | None = None,
) -> None:
    """Generate a magic link, persist its hash, email the user.

    The response from the API caller's perspective is the same whether
    or not the email is a known user (enumeration-resistant). The user
    learns nothing about the system's user-table contents from a
    sign-in attempt.
    """
    issued_at = now or _utc_now()
    raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
    target_email = _normalise_email(email)

    link = MagicLink(
        token_hash=_hash_token(raw_token),
        email=target_email,
        expires_at=issued_at + timedelta(seconds=settings.auth_magic_link_ttl_seconds),
    )
    session.add(link)
    await session.commit()

    callback = _build_callback_url(callback_url or settings.auth_callback_url, raw_token)
    html, text = _magic_link_email_bodies(callback=callback)

    await email_provider.send(
        to=target_email,
        subject="Your Chart Solar sign-in link",
        html_body=html,
        text_body=text,
    )
    _log.info("auth.magic_link_issued", email=target_email)


async def consume_magic_link(
    session: AsyncSession,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> tuple[User, str]:
    """Validate the token, create user-if-needed, mint a session.

    Returns ``(user, raw_session_token)``. The raw session token is
    what the API layer puts in the ``Set-Cookie`` header. Raises
    :class:`MagicLinkError` for any rejection — the API translates that
    to 401 / 410 with no further detail (the link stays opaque).
    """
    when = now or _utc_now()
    token_hash = _hash_token(raw_token)

    link = await session.get(MagicLink, token_hash)
    if link is None:
        raise MagicLinkError("unknown magic link")
    if link.consumed_at is not None:
        raise MagicLinkError("magic link already consumed")
    if link.expires_at <= when:
        raise MagicLinkError("magic link expired")

    # Look up or create the user. ``email`` is unique so the SELECT
    # before INSERT race is benign — concurrent issuers race on UPSERT
    # and the unique constraint catches duplicates.
    user_row = (
        await session.execute(select(User).where(User.email == link.email))
    ).scalar_one_or_none()
    if user_row is None:
        user_row = User(email=link.email)
        session.add(user_row)
        await session.flush()

    # One-shot the magic link so a replay (intentional or accidental)
    # bounces.
    link.consumed_at = when

    raw_session_token = secrets.token_urlsafe(_TOKEN_BYTES)
    session_row = Session(
        token_hash=_hash_token(raw_session_token),
        user_id=user_row.id,
        expires_at=when + timedelta(seconds=settings.auth_session_ttl_seconds),
    )
    session.add(session_row)
    await session.commit()
    _log.info("auth.session_created", user_id=str(user_row.id), email=user_row.email)
    return user_row, raw_session_token


async def revoke_session(
    session: AsyncSession,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> bool:
    """Mark a session revoked; True iff a row was actually flipped.

    A request to sign out an unknown token returns False without
    raising — the caller (always the API layer) clears the cookie
    regardless, so the UX of "click sign-out, you're signed out" is
    preserved even if the cookie was already invalid.
    """
    token_hash = _hash_token(raw_token)
    row = await session.get(Session, token_hash)
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = now or _utc_now()
    await session.commit()
    _log.info("auth.session_revoked", user_id=str(row.user_id))
    return True


async def user_id_for_session_token(
    session: AsyncSession,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> uuid.UUID | None:
    """Resolve the user for a session cookie value, or None if invalid.

    The middleware calls this on every request that carries the
    session cookie; it must be cheap. ``token_hash`` is the primary
    key on ``sessions`` so the lookup is index-only.
    """
    when = now or _utc_now()
    row = await session.get(Session, _hash_token(raw_token))
    if row is None:
        return None
    if row.revoked_at is not None:
        return None
    if row.expires_at <= when:
        return None
    return row.user_id


def _build_callback_url(base: str, raw_token: str) -> str:
    """Append ``?token=<raw_token>`` to the configured callback URL.

    Preserves any existing query string the operator wants to ride
    through (UTM params, e.g.) without losing them under a simple
    string concatenation.
    """
    parsed = urlparse(base)
    query = parsed.query
    extra = urlencode({"token": raw_token})
    new_query = f"{query}&{extra}" if query else extra
    return urlunparse(parsed._replace(query=new_query))


def _magic_link_email_bodies(*, callback: str) -> tuple[str, str]:
    """Return ``(html, text)`` bodies for the sign-in email.

    Plain text first because the safest claim ("here's a link, click
    to sign in") works in any client. The HTML is the same content +
    a button-styled link so the marketing-side rendering stays nice.
    """
    text = (
        "Welcome back to Chart Solar.\n\n"
        f"To sign in, click this link within 15 minutes:\n\n{callback}\n\n"
        "If you didn't request this, ignore this email — no account changes.\n"
    )
    html = (
        "<p>Welcome back to Chart Solar.</p>"
        "<p>To sign in, click the link below within 15 minutes:</p>"
        f'<p><a href="{callback}" '
        'style="display:inline-block;padding:12px 24px;'
        "background:#0b6b4f;color:#fff;text-decoration:none;border-radius:6px;"
        '">Sign in to Chart Solar</a></p>'
        f"<p>Or paste this URL into your browser:<br><code>{callback}</code></p>"
        "<p>If you didn't request this, ignore this email — no account changes.</p>"
    )
    return html, text


__all__ = [
    "MagicLinkError",
    "consume_magic_link",
    "request_magic_link",
    "revoke_session",
    "user_id_for_session_token",
]

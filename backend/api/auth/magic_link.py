"""POST /api/auth/login, GET /api/auth/callback, POST /api/auth/logout.

Three thin endpoints over ``backend.services.auth_service``:

* ``POST /api/auth/login`` — accept an email; generate + email a
  magic link. Always 200 — does not reveal whether the email is a
  known user (enumeration-resistant).
* ``GET /api/auth/callback?token=…`` — consume a magic link, set the
  session cookie, return ``{user: …}``. The frontend renders the
  callback URL and POSTs no body; this is the API the magic-link
  email actually points at via the ``auth_callback_url`` setting.
* ``POST /api/auth/logout`` — read the session cookie, mark the
  session revoked, clear the cookie.

Keeping this module thin so the actual mechanism (token hashing, user
upsert, session minting) lives in ``services/auth_service`` and is
exercised independently of FastAPI.
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

import backend.database as _db
from backend.config import settings
from backend.infra.logging import get_logger
from backend.infra.rate_limit import (
    LOGIN_PER_EMAIL_LIMIT,
    LOGIN_PER_EMAIL_WINDOW_SECONDS,
    LOGIN_PER_IP_LIMIT,
    LOGIN_PER_IP_WINDOW_SECONDS,
    check_rate_limit,
    get_rate_limit_redis,
    per_ip_dependency,
)
from backend.providers.email.resend import ResendEmailProvider
from backend.services.auth_service import (
    MagicLinkError,
    consume_magic_link,
    issue_magic_link,
    revoke_session,
    send_magic_link_email,
)

router = APIRouter()
_log = get_logger(__name__)

_login_per_ip_throttle = per_ip_dependency(
    bucket="login_ip",
    limit=LOGIN_PER_IP_LIMIT,
    window_seconds=LOGIN_PER_IP_WINDOW_SECONDS,
)


class LoginRequest(BaseModel):
    email: EmailStr


@router.post("/auth/login", dependencies=[Depends(_login_per_ip_throttle)])
async def login(request: Request, payload: LoginRequest) -> dict[str, str]:
    """Request a magic-link sign-in email.

    Always 200 — the response shape doesn't change whether the email
    matches a known user. Operator probing for "is bob@example.com a
    user" gets the same answer either way.

    Rate-limited two ways: the per-IP throttle on the route stops
    bulk volume from a single attacker; the per-email throttle below
    stops a distributed attack from spamming a specific inbox via
    Resend (which we are billed for and whose deliverability we depend
    on). Both 429 with no email-existence side-channel.

    The DB write and the Resend send are split: we close the session
    before invoking the email provider so a slow Resend round-trip
    cannot park a Postgres connection.
    """
    email = str(payload.email).strip().lower()

    # Per-email bucket — must come after the body parses so we have the
    # email; the per-IP throttle (route-level Depends above) already ran.
    redis_client = get_rate_limit_redis()
    allowed = await check_rate_limit(
        redis_client,
        key=f"rl:login_email:{email}",
        limit=LOGIN_PER_EMAIL_LIMIT,
        window_seconds=LOGIN_PER_EMAIL_WINDOW_SECONDS,
    )
    if not allowed:
        _log.warning("auth.login_rate_limited", scope="email")
        # Same 429 shape as the per-IP throttle so the client can't
        # distinguish "this email is throttled" from "your IP is throttled".
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded; try again later",
        )

    email_provider = ResendEmailProvider()
    async with _db.SessionLocal() as session:
        pending = await issue_magic_link(session, email=email)
    await send_magic_link_email(email_provider, pending)
    return {"status": "magic_link_sent"}


@router.get("/auth/callback")
async def callback(token: str) -> Response:
    """Consume the magic link, set the session cookie.

    Returns JSON so the frontend can show "Welcome back, …". The
    cookie is HTTP-only + SameSite=lax + Secure (configurable via
    ``auth_session_cookie_secure`` for local dev over plain http).
    """
    async with _db.SessionLocal() as session:
        try:
            user, session_token = await consume_magic_link(session, raw_token=token)
        except MagicLinkError as exc:
            # 410 Gone is the most-correct status: the link existed
            # (or could have) but is no longer usable. The detail is
            # opaque to the client — the message stays in the log.
            _log.info("auth.magic_link_rejected", reason=str(exc))
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="magic link is invalid or expired",
            ) from exc

    response = JSONResponse({"user": {"id": str(user.id), "email": user.email}})
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        max_age=settings.auth_session_ttl_seconds,
        httponly=True,
        secure=settings.auth_session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/auth/logout")
async def logout(
    response: Response,
    session_cookie: str | None = Cookie(default=None, alias=settings.auth_session_cookie_name),
) -> dict[str, str]:
    """Revoke the session, clear the cookie.

    Always 200 — clearing the cookie is the user-visible effect, and
    the user perceives "I'm signed out" regardless of whether the
    session row actually existed.
    """
    if session_cookie:
        async with _db.SessionLocal() as session:
            await revoke_session(session, raw_token=session_cookie)

    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path="/",
    )
    return {"status": "signed_out"}

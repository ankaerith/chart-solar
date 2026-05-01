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

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

import backend.database as _db
from backend.config import settings
from backend.infra.logging import get_logger
from backend.providers.email.resend import ResendEmailProvider
from backend.services.auth_service import (
    MagicLinkError,
    consume_magic_link,
    request_magic_link,
    revoke_session,
)

router = APIRouter()
_log = get_logger(__name__)


class LoginRequest(BaseModel):
    email: EmailStr


@router.post("/auth/login")
async def login(payload: LoginRequest) -> dict[str, str]:
    """Request a magic-link sign-in email.

    Always 200 — the response shape doesn't change whether the email
    matches a known user. Operator probing for "is bob@example.com a
    user" gets the same answer either way.
    """
    email_provider = ResendEmailProvider()
    async with _db.SessionLocal() as session:
        await request_magic_link(
            session,
            email_provider,
            email=str(payload.email),
        )
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

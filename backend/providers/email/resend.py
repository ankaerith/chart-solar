"""Resend HTTP API adapter.

Thin wrapper over Resend's ``POST /emails`` endpoint. Pulls the
project's shared ``infra.http.make_post`` so the call rides the same
retry + circuit-breaker the rest of the providers use; the
``test_no_raw_httpx_outside_infra`` guardrail blocks raw httpx outside
``backend/infra/`` so this is the only honest way to talk to Resend.

The Resend Python SDK is intentionally not used: it's a 10MB transitive
surface for one endpoint that's stable and well-documented
(https://resend.com/docs/api-reference/emails/send-email).
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import require, settings
from backend.infra.http import make_post
from backend.providers.email import EmailError, SentEmail

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailProvider:
    """``EmailProvider`` backed by Resend's HTTP API."""

    name = "resend"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        from_email: str | None = None,
    ) -> None:
        self._api_key = require(api_key or settings.resend_api_key, "RESEND_API_KEY")
        self._default_from = from_email or settings.resend_from_email
        # ``make_post`` returns a retry+circuit-breaker-wrapped callable
        # bound to the ``resend`` service key. Multiple instances share
        # the same breaker so a sustained Resend outage trips once.
        self._post = make_post(service="resend")

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: str | None = None,
    ) -> SentEmail:
        payload: dict[str, Any] = {
            "from": from_email or self._default_from,
            "to": [to],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }
        try:
            resp = await self._post(
                RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.HTTPStatusError as exc:
            raise EmailError(
                f"resend rejected send (HTTP {exc.response.status_code}): {exc.response.text[:256]}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 — wrap for the API layer
            raise EmailError(f"resend transport failed: {exc!r}") from exc

        body = resp.json() if resp.content else {}
        message_id = body.get("id") if isinstance(body, dict) else None
        return SentEmail(to=to, subject=subject, provider_message_id=message_id)


__all__ = ["ResendEmailProvider"]

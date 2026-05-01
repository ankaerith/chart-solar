"""EmailProvider port — transactional email send.

The magic-link flow is the first caller (chart-solar-ij9); future
audit-completion notifications + Track digests will reach for the
same Protocol so swapping providers (Resend → Postmark → SES) is one
DI binding away. Live adapter is :class:`backend.providers.email.resend`;
tests + offline dev use :class:`backend.providers.fake.FakeEmailProvider`.

The Protocol is narrow on purpose: ``send`` takes a single recipient,
subject, and both an HTML body and a plain-text body. Multi-recipient
or templated sends layer on top of this; the Protocol stays minimal so
adapters are trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class EmailError(RuntimeError):
    """Raised when an upstream email send fails."""


@dataclass(frozen=True)
class SentEmail:
    """Receipt for an email the upstream accepted for delivery.

    ``provider_message_id`` is whatever the upstream returned (Resend's
    ``id``, SES's ``MessageId``, …) so callers can correlate later
    bounces / opens with the originating send.
    """

    to: str
    subject: str
    provider_message_id: str | None = None


@runtime_checkable
class EmailProvider(Protocol):
    """Send a single transactional email."""

    name: str

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: str | None = None,
    ) -> SentEmail:
        """Hand the message to the upstream; return a delivery receipt.

        Implementations MUST raise :class:`EmailError` on any upstream
        failure (auth, rate-limit, malformed payload). The magic-link
        flow translates that to a 502 to the user.
        """
        ...


__all__ = ["EmailError", "EmailProvider", "SentEmail"]

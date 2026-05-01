"""In-memory ``EmailProvider`` for tests + offline dev.

Records each send into ``sent`` so tests can assert against the
captured payload (subject, body, recipient) without a real outbound
connection. Magic-link tests use this to extract the link the user
would have clicked.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.providers.email import SentEmail


@dataclass
class _Outbox:
    to: str
    subject: str
    html_body: str
    text_body: str
    from_email: str | None


class FakeEmailProvider:
    """In-memory ``EmailProvider``. Captures every send into ``sent``."""

    name = "fake"

    def __init__(self) -> None:
        self.sent: list[_Outbox] = []

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        text_body: str,
        from_email: str | None = None,
    ) -> SentEmail:
        self.sent.append(
            _Outbox(
                to=to,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_email=from_email,
            )
        )
        return SentEmail(to=to, subject=subject, provider_message_id=f"fake_{len(self.sent)}")


__all__ = ["FakeEmailProvider"]

"""Sliding-window rate limiter — bucket math + fail-open behaviour."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.config import settings
from backend.infra.rate_limit import _client_ip, check_rate_limit


class _FakeRedis:
    """Minimal in-memory async redis double — exposes incr + expire."""

    def __init__(self, *, raise_on: str | None = None) -> None:
        self._counts: dict[str, int] = {}
        self._raise_on = raise_on

    async def incr(self, key: str) -> int:
        if self._raise_on == "incr":
            raise ConnectionError("redis is sick")
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        if self._raise_on == "expire":
            raise ConnectionError("redis is sick")
        return True


async def test_check_rate_limit_allows_under_limit() -> None:
    redis = _FakeRedis()
    for _ in range(5):
        assert await check_rate_limit(
            redis,  # type: ignore[arg-type]
            key="rl:test:user",
            limit=5,
            window_seconds=60,
        )


async def test_check_rate_limit_refuses_at_and_beyond_limit() -> None:
    redis = _FakeRedis()
    for _ in range(3):
        await check_rate_limit(
            redis,  # type: ignore[arg-type]
            key="rl:test:user",
            limit=3,
            window_seconds=60,
        )
    # The 4th call has count=4 > limit=3 → False.
    assert not await check_rate_limit(
        redis,  # type: ignore[arg-type]
        key="rl:test:user",
        limit=3,
        window_seconds=60,
    )


async def test_check_rate_limit_separates_buckets_by_key() -> None:
    redis = _FakeRedis()
    for _ in range(3):
        await check_rate_limit(
            redis,  # type: ignore[arg-type]
            key="rl:test:alice",
            limit=3,
            window_seconds=60,
        )
    # Bob's bucket is independent.
    assert await check_rate_limit(
        redis,  # type: ignore[arg-type]
        key="rl:test:bob",
        limit=3,
        window_seconds=60,
    )


@pytest.mark.parametrize("raise_on", ["incr", "expire"])
async def test_check_rate_limit_fails_open_on_redis_failure(raise_on: str) -> None:
    """A Redis outage must not lock everyone out — fail-open is the
    documented contract; the rest of the stack treats Redis as soft."""
    redis: Any = _FakeRedis(raise_on=raise_on)
    assert await check_rate_limit(
        redis,
        key="rl:test:any",
        limit=1,
        window_seconds=60,
    )


def _request_with(*, peer: str | None, xff: str | None) -> Any:
    """Stub a Starlette ``Request`` exposing only ``client.host`` + headers."""
    headers = {"x-forwarded-for": xff} if xff is not None else {}
    request = MagicMock()
    request.client = MagicMock(host=peer) if peer is not None else None
    request.headers = headers
    return request


def test_client_ip_ignores_xff_when_zero_trusted_hops(monkeypatch: pytest.MonkeyPatch) -> None:
    """XFF must not influence the bucket key on a deploy that doesn't
    declare any trusted proxies — otherwise an attacker cycling XFF
    values bypasses the per-IP rate limit."""
    monkeypatch.setattr(settings, "trust_forwarded_for_hops", 0)
    request = _request_with(peer="127.0.0.1", xff="9.9.9.9")
    assert _client_ip(request) == "127.0.0.1"


def test_client_ip_peels_one_hop_when_one_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trust_forwarded_for_hops", 1)
    # One proxy in front: the rightmost (and only) XFF entry is the client.
    request = _request_with(peer="10.0.0.1", xff="203.0.113.5")
    assert _client_ip(request) == "203.0.113.5"


def test_client_ip_falls_back_to_peer_on_xff_misconfig(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operator declared 2 trusted hops but only 1 XFF entry showed up —
    bucketing on the trusted-proxy peer is safer than trusting an XFF
    entry that may have been client-supplied."""
    monkeypatch.setattr(settings, "trust_forwarded_for_hops", 2)
    request = _request_with(peer="10.0.0.1", xff="9.9.9.9")
    assert _client_ip(request) == "10.0.0.1"

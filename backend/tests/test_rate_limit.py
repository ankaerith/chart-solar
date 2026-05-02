"""Sliding-window rate limiter — bucket math + fail-open behaviour."""

from __future__ import annotations

from typing import Any

import pytest

from backend.infra.rate_limit import check_rate_limit


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

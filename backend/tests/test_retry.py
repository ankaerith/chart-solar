"""Retry + circuit-breaker behaviour, plus the no-raw-httpx-outside-infra rule."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.infra.logging import configure_logging, set_correlation_id
from backend.infra.retry import (
    CircuitOpenError,
    RetryConfig,
    RetryExhaustedError,
    reset_breakers,
    retry,
)

FAST_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay_s=0.0,
    max_delay_s=0.0,
    jitter_s=0.0,
    breaker_threshold=3,
    breaker_cooldown_s=60.0,
)


@pytest.fixture(autouse=True)
def _reset_breakers() -> Iterator[None]:
    reset_breakers()
    yield
    reset_breakers()


def test_sync_recovers_after_transient_failure() -> None:
    calls = {"n": 0}

    @retry(service="svc-sync-transient", config=FAST_CONFIG)
    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


async def test_async_recovers_after_transient_failure() -> None:
    calls = {"n": 0}

    @retry(service="svc-async-transient", config=FAST_CONFIG)
    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert await flaky() == "ok"
    assert calls["n"] == 2


def test_sync_exhausts_then_raises() -> None:
    calls = {"n": 0}

    @retry(service="svc-sync-exhaust", config=FAST_CONFIG)
    def always_fails() -> None:
        calls["n"] += 1
        raise RuntimeError("nope")

    with pytest.raises(RetryExhaustedError) as ei:
        always_fails()

    assert calls["n"] == FAST_CONFIG.max_attempts
    assert ei.value.attempts == FAST_CONFIG.max_attempts
    assert ei.value.service == "svc-sync-exhaust"
    assert isinstance(ei.value.last_error, RuntimeError)


def test_non_retryable_exception_bubbles_immediately() -> None:
    calls = {"n": 0}

    @retry(service="svc-narrow", config=FAST_CONFIG, retry_on=(TimeoutError,))
    def raises_value_error() -> None:
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        raises_value_error()

    assert calls["n"] == 1


def test_circuit_opens_after_threshold_then_fails_fast() -> None:
    calls = {"n": 0}

    # max_attempts=1 so each call counts as exactly one breaker failure.
    cfg = RetryConfig(
        max_attempts=1,
        base_delay_s=0.0,
        max_delay_s=0.0,
        jitter_s=0.0,
        breaker_threshold=3,
        breaker_cooldown_s=60.0,
    )

    @retry(service="svc-trip", config=cfg)
    def always_fails() -> None:
        calls["n"] += 1
        raise RuntimeError("upstream down")

    for _ in range(3):
        with pytest.raises(RetryExhaustedError):
            always_fails()

    assert calls["n"] == 3

    # Breaker is now open: next call short-circuits before invoking the function.
    with pytest.raises(CircuitOpenError):
        always_fails()
    assert calls["n"] == 3


def test_circuit_recovers_after_cooldown() -> None:
    calls = {"n": 0}
    cfg = RetryConfig(
        max_attempts=1,
        base_delay_s=0.0,
        max_delay_s=0.0,
        jitter_s=0.0,
        breaker_threshold=2,
        breaker_cooldown_s=0.05,
    )

    @retry(service="svc-recover", config=cfg)
    def maybe_fails() -> str:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("transient")
        return "ok"

    for _ in range(2):
        with pytest.raises(RetryExhaustedError):
            maybe_fails()

    # Open — fails fast.
    with pytest.raises(CircuitOpenError):
        maybe_fails()
    assert calls["n"] == 2  # function not invoked while open

    # Cooldown elapses → half-open → success closes the breaker.
    time.sleep(0.06)
    assert maybe_fails() == "ok"


def test_per_service_breakers_are_isolated() -> None:
    cfg = RetryConfig(
        max_attempts=1,
        base_delay_s=0.0,
        max_delay_s=0.0,
        jitter_s=0.0,
        breaker_threshold=2,
        breaker_cooldown_s=60.0,
    )

    @retry(service="svc-a", config=cfg)
    def a() -> None:
        raise RuntimeError("a-down")

    @retry(service="svc-b", config=cfg)
    def b() -> str:
        return "b-up"

    for _ in range(2):
        with pytest.raises(RetryExhaustedError):
            a()
    # svc-a is now open — but svc-b should be entirely unaffected.
    assert b() == "b-up"


def test_failure_log_includes_service_and_correlation_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(service="test")
    set_correlation_id("cid-7777")
    try:
        calls = {"n": 0}

        @retry(service="svc-log", config=FAST_CONFIG)
        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("boom")
            return "ok"

        flaky()
    finally:
        set_correlation_id(None)

    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.splitlines() if ln.startswith("{")]
    payloads = [json.loads(ln) for ln in lines]
    failures = [p for p in payloads if p.get("event") == "retry.attempt_failed"]
    assert failures, f"no retry.attempt_failed log emitted: {payloads}"
    record = failures[0]
    assert record["service"] == "svc-log"
    assert record["correlation_id"] == "cid-7777"
    assert record["error_type"] == "RuntimeError"
    assert record["attempt"] == 1


async def test_async_exhausts_then_raises() -> None:
    @retry(service="svc-async-exhaust", config=FAST_CONFIG)
    async def always_fails() -> None:
        raise RuntimeError("nope")

    with pytest.raises(RetryExhaustedError):
        await always_fails()


async def test_async_circuit_opens() -> None:
    cfg = RetryConfig(
        max_attempts=1,
        base_delay_s=0.0,
        max_delay_s=0.0,
        jitter_s=0.0,
        breaker_threshold=3,
        breaker_cooldown_s=60.0,
    )

    @retry(service="svc-async-trip", config=cfg)
    async def always_fails() -> None:
        raise RuntimeError("down")

    for _ in range(3):
        with pytest.raises(RetryExhaustedError):
            await always_fails()
    with pytest.raises(CircuitOpenError):
        await always_fails()


def test_no_raw_httpx_outside_infra() -> None:
    """Every external HTTP call goes through `backend/infra/*`, where it gets the
    `@retry` wrapper. Constructing `httpx.Client(...)` or `httpx.AsyncClient(...)`
    or calling top-level `httpx.get/post/...` outside `backend/infra/` is banned —
    add a wrapper in infra/ instead. (acceptance criterion 3)
    """
    backend_root = Path(__file__).resolve().parent.parent
    forbidden = re.compile(
        r"\bhttpx\.(?:Client|AsyncClient|get|post|put|patch|delete|request|stream)\s*\("
    )
    offenders: list[str] = []
    for path in backend_root.rglob("*.py"):
        rel = path.relative_to(backend_root.parent)
        parts = rel.parts
        if "infra" in parts or "tests" in parts:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if forbidden.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "raw httpx usage outside backend/infra/ — wrap it in infra and use @retry:\n"
        + "\n".join(offenders)
    )

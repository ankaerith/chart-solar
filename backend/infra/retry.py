"""Retry + circuit-breaker for external calls.

Every upstream HTTP / API call (NSRDB, PVGIS, Open-Meteo, Vertex AI, Stripe
read-side, Enphase, SolarEdge, Octopus, n3rgy …) is wrapped with `@retry`
so transient failures are absorbed with exponential backoff + jitter, and a
per-service circuit-breaker trips after sustained failure to stop hammering
a sick upstream.

Usage:

    @retry(service="nsrdb")
    async def fetch_psm3(year: int) -> bytes:
        async with httpx.AsyncClient() as client:
            ...

The breaker is keyed on `service`; each upstream gets its own. Logs land
through `structlog` with `service`, `attempt`, `error_type`, and the active
`correlation_id` so a single forecast can be traced across providers.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from backend.infra.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitOpenError(RuntimeError):
    """Raised when a service's circuit-breaker is open and rejecting calls."""

    def __init__(self, service: str, opened_at: float) -> None:
        self.service = service
        self.opened_at = opened_at
        super().__init__(f"circuit-breaker open for service={service!r}")


class RetryExhaustedError(RuntimeError):
    """Raised when @retry has used its full budget and the call still fails."""

    def __init__(self, service: str, attempts: int, last_error: BaseException) -> None:
        self.service = service
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"retry exhausted for service={service!r} after {attempts} attempt(s): {last_error!r}"
        )


@dataclass(frozen=True)
class RetryConfig:
    """Per-call retry policy. Pass ``config=`` to override the default."""

    max_attempts: int = 4
    base_delay_s: float = 0.2
    max_delay_s: float = 5.0
    jitter_s: float = 0.1
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 60.0


DEFAULT_CONFIG = RetryConfig()


class CircuitBreaker:
    """A single closed → open → half-open → closed breaker.

    Closed: calls pass through; consecutive failures count up.
    Open:   calls fail fast with `CircuitOpenError` until cooldown elapses.
    Half-open: the next call probes the upstream; success closes, failure
              re-opens (with a fresh cooldown).
    """

    def __init__(self, service: str, threshold: int, cooldown_s: float) -> None:
        self.service = service
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None

    def before_call(self, now: float) -> None:
        """Raise `CircuitOpenError` if the breaker is open and not yet cooled down."""
        with self._lock:
            if self._opened_at is None:
                return
            if now - self._opened_at < self.cooldown_s:
                raise CircuitOpenError(self.service, self._opened_at)
            # Cooldown elapsed — move to half-open: let the next call probe.

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self, now: float) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.threshold:
                self._opened_at = now

    def reset(self) -> None:
        """Test affordance — drop all state."""
        with self._lock:
            self._failures = 0
            self._opened_at = None


_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def _get_breaker(service: str, config: RetryConfig) -> CircuitBreaker:
    with _breakers_lock:
        breaker = _breakers.get(service)
        if breaker is None:
            breaker = CircuitBreaker(service, config.breaker_threshold, config.breaker_cooldown_s)
            _breakers[service] = breaker
        return breaker


def reset_breakers() -> None:
    """Test affordance — clear every breaker's state between tests."""
    with _breakers_lock:
        for breaker in _breakers.values():
            breaker.reset()


def _backoff_seconds(attempt: int, config: RetryConfig) -> float:
    """Exponential backoff (`base * 2^(attempt-1)`) capped at `max_delay_s`, plus jitter."""
    delay = min(config.base_delay_s * (2.0 ** (attempt - 1)), config.max_delay_s)
    jitter: float = random.uniform(0.0, config.jitter_s)
    return delay + jitter


def retry(
    *,
    service: str,
    config: RetryConfig | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorate a sync or async callable with retry + circuit-breaker.

    `service` is the breaker key (e.g. ``"nsrdb"``, ``"vertex"``).
    `retry_on` narrows which exceptions trigger a retry; everything else
    bubbles up immediately. `CircuitOpenError` is never retried.
    """
    cfg = config or DEFAULT_CONFIG

    def decorator(func: F) -> F:
        breaker = _get_breaker(service, cfg)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Check the breaker once at call entry: a sick upstream fails
                # fast with CircuitOpenError instead of burning the retry budget.
                breaker.before_call(time.monotonic())
                last_error: BaseException | None = None
                for attempt in range(1, cfg.max_attempts + 1):
                    try:
                        result = await func(*args, **kwargs)
                    except retry_on as exc:
                        last_error = exc
                        breaker.record_failure(time.monotonic())
                        logger.warning(
                            "retry.attempt_failed",
                            service=service,
                            attempt=attempt,
                            max_attempts=cfg.max_attempts,
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                        if attempt == cfg.max_attempts:
                            break
                        await asyncio.sleep(_backoff_seconds(attempt, cfg))
                        continue
                    breaker.record_success()
                    return result
                assert last_error is not None
                raise RetryExhaustedError(service, cfg.max_attempts, last_error) from last_error

            return cast(F, async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            breaker.before_call(time.monotonic())
            last_error: BaseException | None = None
            for attempt in range(1, cfg.max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                except retry_on as exc:
                    last_error = exc
                    breaker.record_failure(time.monotonic())
                    logger.warning(
                        "retry.attempt_failed",
                        service=service,
                        attempt=attempt,
                        max_attempts=cfg.max_attempts,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                    if attempt == cfg.max_attempts:
                        break
                    time.sleep(_backoff_seconds(attempt, cfg))
                    continue
                breaker.record_success()
                return result
            assert last_error is not None
            raise RetryExhaustedError(service, cfg.max_attempts, last_error) from last_error

        return cast(F, sync_wrapper)

    return decorator

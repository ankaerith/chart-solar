"""Structured logging with correlation IDs.

JSON output, ISO-8601 timestamps, level-tagged. A single `correlation_id`
flows from HTTP request → API handler → enqueue (job meta) → worker →
external calls so a "forecast stuck" investigation pivots cleanly across
processes.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from backend.config import settings

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def _bind_correlation(
    _: Any, __: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    cid = _correlation_id.get()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
        if settings.sentry_dsn:
            sentry_sdk.set_tag("correlation_id", cid)
    return event_dict


def _bind_service(service: str) -> structlog.types.Processor:
    def processor(
        _: Any, __: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service", service)
        return event_dict

    return processor


def configure_logging(service: str) -> None:
    """Wire structlog + stdlib logging + Sentry. Idempotent — safe to call twice."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _bind_service(service),
            _bind_correlation,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            integrations=[FastApiIntegration(), StarletteIntegration()],
            traces_sample_rate=0.0,
        )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]

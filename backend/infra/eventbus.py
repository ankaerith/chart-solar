"""In-process pub/sub for cross-cutting side effects.

Side effects (entitlement grant, regional aggregate refresh, email send,
Sentry breadcrumbs) shouldn't get hard-wired into the engine, audit, or
payment paths. Publishers call :func:`dispatch` with a typed event
payload; subscribers register via :func:`subscribe` keyed on the event
class. The bus is in-process — Postgres LISTEN/NOTIFY can replace it
when a side effect needs to cross processes.

Properties:

* **Type-routed.** Subscribers register against an event class; the
  dispatcher walks ``type(event).__mro__`` so a registered ``_BaseEvent``
  catches every event (used by the structured-error logger). Anything
  else routes by exact subclass.
* **Failure-isolated.** A subscriber that raises has its exception
  swallowed *after* a structured log line that includes the event
  payload + correlation id; the publisher never sees it. Order of
  invocation is registration order; the bus does not guarantee any
  cross-event ordering.
* **No retries.** Subscribers are responsible for their own retry +
  idempotency. The :class:`PaymentSucceeded` grant subscriber, for
  example, dedupes on ``stripe_event_id`` before touching state.
* **Test seam.** Tests reset registrations via :func:`clear_subscribers`
  in a fixture so handlers don't leak between cases.
"""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable

from backend.domain.events import _BaseEvent
from backend.infra.logging import get_correlation_id, get_logger

#: Subscribers may be sync or async. ``dispatch`` invokes only the sync
#: ones (and warns on async); ``dispatch_async`` awaits both. The
#: webhook hot path uses ``dispatch_async`` so an async grant subscriber
#: completes before we 200 the upstream caller.
SyncHandler = Callable[[_BaseEvent], None]
AsyncHandler = Callable[[_BaseEvent], Awaitable[None]]
Handler = SyncHandler | AsyncHandler

_log = get_logger(__name__)

_HANDLERS: dict[type[_BaseEvent], list[Handler]] = defaultdict(list)


def subscribe[E: _BaseEvent](
    event_type: type[E],
) -> Callable[[Callable[[E], None] | Callable[[E], Awaitable[None]]], Callable[..., object]]:
    """Decorator: register a sync or async handler for ``event_type``.

    Usage::

        @subscribe(PaymentSucceeded)
        async def grant_entitlement(event: PaymentSucceeded) -> None:
            async with SessionLocal() as session:
                await grant_tier(session, ...)

    Sync handlers run on every dispatch path (``dispatch`` and
    ``dispatch_async``); async handlers are skipped by sync ``dispatch``
    with a warning so a wrong-path call site is loud.
    """

    def decorator(
        handler: Callable[[E], None] | Callable[[E], Awaitable[None]],
    ) -> Callable[..., object]:
        # The `_HANDLERS` map is invariant in handler signature — it
        # stores `Callable[[_BaseEvent], …]`. Subscribers register the
        # narrower `Callable[[E], …]`; the dispatcher only ever invokes
        # a handler with an event whose type is `E` or narrower (the
        # cls-keyed lookup), so the cast is safe.
        _HANDLERS[event_type].append(handler)  # type: ignore[arg-type]
        return handler

    return decorator


def dispatch(event: _BaseEvent) -> None:
    """Notify every sync handler registered for ``type(event)`` or any base.

    Walks the MRO so a handler registered on ``_BaseEvent`` (typically
    a logging or metrics shim) catches everything. Async handlers are
    *not* invoked here — call ``await dispatch_async(event)`` instead.
    Subscriber failures are caught + logged with the event payload +
    correlation id; the publisher never sees them.
    """
    cid = get_correlation_id()
    for handler, _ in _walk(event):
        if inspect.iscoroutinefunction(handler):
            _log.warning(
                "eventbus.async_handler_skipped_by_sync_dispatch",
                handler=getattr(handler, "__qualname__", repr(handler)),
                event_type=type(event).__name__,
                hint="use await dispatch_async(event) for async subscribers",
            )
            continue
        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001 — bus must not propagate
            _log.error(
                "eventbus.handler_failed",
                handler=getattr(handler, "__qualname__", repr(handler)),
                event_type=type(event).__name__,
                event_id=event.event_id,
                correlation_id=cid,
                error=repr(exc),
            )


async def dispatch_async(event: _BaseEvent) -> None:
    """Notify every handler — sync or async — registered for ``event``.

    Async handlers are awaited in registration order; sync handlers run
    inline. Both share the same failure isolation as ``dispatch``: an
    exception is logged with payload + correlation id and never
    propagates to the publisher. The Stripe webhook calls this so the
    entitlement grant completes before the 200 lands back at Stripe.
    """
    cid = get_correlation_id()
    for handler, _ in _walk(event):
        try:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as exc:  # noqa: BLE001 — bus must not propagate
            _log.error(
                "eventbus.handler_failed",
                handler=getattr(handler, "__qualname__", repr(handler)),
                event_type=type(event).__name__,
                event_id=event.event_id,
                correlation_id=cid,
                error=repr(exc),
            )


def _walk(event: _BaseEvent) -> list[tuple[Handler, type[_BaseEvent]]]:
    """Collect handlers for ``type(event)`` and every base class above it."""
    out: list[tuple[Handler, type[_BaseEvent]]] = []
    for cls in type(event).__mro__:
        if cls is object:
            continue
        for handler in _HANDLERS.get(cls, ()):
            out.append((handler, cls))
    return out


def clear_subscribers() -> None:
    """Drop every registration. Test-only; production code never calls this."""
    _HANDLERS.clear()


__all__ = ["clear_subscribers", "dispatch", "dispatch_async", "subscribe"]

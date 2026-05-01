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

from collections import defaultdict
from collections.abc import Callable

from backend.domain.events import _BaseEvent
from backend.infra.logging import get_correlation_id, get_logger

Handler = Callable[[_BaseEvent], None]

_log = get_logger(__name__)

_HANDLERS: dict[type[_BaseEvent], list[Handler]] = defaultdict(list)


def subscribe[E: _BaseEvent](
    event_type: type[E],
) -> Callable[[Callable[[E], None]], Callable[[E], None]]:
    """Decorator: register a handler for events of (or extending) ``event_type``.

    Usage::

        @subscribe(PaymentSucceeded)
        def grant_entitlement(event: PaymentSucceeded) -> None:
            ...

    The returned function is the original handler so call sites can
    still invoke it directly (handy for unit tests). Registrations are
    process-local; a fork() crosses a boundary and the new process
    won't see the parent's handlers.
    """

    def decorator(handler: Callable[[E], None]) -> Callable[[E], None]:
        # The `_HANDLERS` map is invariant in handler signature — it
        # stores `Callable[[_BaseEvent], None]`. Subscribers register
        # the narrower `Callable[[E], None]`; the dispatcher only ever
        # invokes a handler with an event whose type is `E` or
        # narrower (the cls-keyed lookup), so the cast is safe.
        _HANDLERS[event_type].append(handler)  # type: ignore[arg-type]
        return handler

    return decorator


def dispatch(event: _BaseEvent) -> None:
    """Notify every handler registered for ``type(event)`` or any base.

    Walks the MRO so a handler registered on ``_BaseEvent`` (typically
    a logging or metrics shim) catches everything. Subscriber failures
    are caught + logged with the event payload + correlation id so the
    publisher can complete its own work; the failed handler does not
    abort delivery to siblings.
    """
    cid = get_correlation_id()
    for cls in type(event).__mro__:
        if cls is object:
            continue
        for handler in _HANDLERS.get(cls, ()):
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


def clear_subscribers() -> None:
    """Drop every registration. Test-only; production code never calls this."""
    _HANDLERS.clear()


__all__ = ["clear_subscribers", "dispatch", "subscribe"]

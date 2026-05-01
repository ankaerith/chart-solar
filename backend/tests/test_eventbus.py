"""In-process event bus: routing, isolation, idempotency.

Covers the four properties the bus owes its callers:

* type-routed dispatch (subclass + base-class handlers both fire)
* failure isolation (a raising subscriber doesn't break siblings or
  bubble out to the publisher)
* dedupe at the subscriber via the event's stable id (Stripe replay
  scenario — the canonical idempotency case from chart-solar-j1gc)
* registration teardown (so handlers don't leak between tests)
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from backend.domain.events import (
    ForecastCompleted,
    PaymentSucceeded,
    _BaseEvent,
)
from backend.entitlements.features import Tier
from backend.infra.eventbus import clear_subscribers, dispatch, subscribe


@pytest.fixture(autouse=True)
def _isolate_subscribers() -> Iterator[None]:
    """Reset registrations around each test so handlers don't leak."""
    clear_subscribers()
    yield
    clear_subscribers()


def test_dispatch_invokes_subscribed_handler() -> None:
    received: list[PaymentSucceeded] = []

    @subscribe(PaymentSucceeded)
    def handler(event: PaymentSucceeded) -> None:
        received.append(event)

    event = PaymentSucceeded(user_id="u1", tier=Tier.TRACK, stripe_event_id="evt_1")
    dispatch(event)

    assert received == [event]


def test_dispatch_skips_handlers_for_unrelated_events() -> None:
    """A ForecastCompleted handler must not see a PaymentSucceeded."""
    received: list[ForecastCompleted] = []

    @subscribe(ForecastCompleted)
    def forecast_handler(event: ForecastCompleted) -> None:
        received.append(event)

    dispatch(PaymentSucceeded(user_id="u1", tier=Tier.FREE, stripe_event_id="evt_1"))
    assert received == []


def test_dispatch_walks_mro_so_base_class_subscribers_catch_everything() -> None:
    """A `_BaseEvent` subscriber acts as a logging shim — every event
    hits it regardless of concrete type."""
    seen: list[str] = []

    @subscribe(_BaseEvent)
    def metric_shim(event: _BaseEvent) -> None:
        seen.append(type(event).__name__)

    dispatch(PaymentSucceeded(user_id="u1", tier=Tier.FREE, stripe_event_id="evt_1"))
    dispatch(ForecastCompleted(job_id="j1", user_id="u1", result_summary={"artifact_keys": []}))
    assert seen == ["PaymentSucceeded", "ForecastCompleted"]


def test_subscriber_failure_is_isolated_and_does_not_break_publisher() -> None:
    """A handler that raises must NOT abort delivery to siblings, and
    the publisher's `dispatch` call must complete normally."""
    sibling_called = []

    @subscribe(PaymentSucceeded)
    def buggy(event: PaymentSucceeded) -> None:
        raise RuntimeError("downstream is on fire")

    @subscribe(PaymentSucceeded)
    def sibling(event: PaymentSucceeded) -> None:
        sibling_called.append(event.user_id)

    dispatch(PaymentSucceeded(user_id="u1", tier=Tier.FREE, stripe_event_id="evt_1"))
    assert sibling_called == ["u1"]


def test_payment_grant_subscriber_is_idempotent_on_replay() -> None:
    """Stripe re-delivers webhooks on receiver timeout. The grant
    subscriber must dedupe on `stripe_event_id` so the user is credited
    once even when the same event arrives twice — the headline scenario
    from the chart-solar-j1gc acceptance criteria."""
    granted_tiers: dict[str, str] = {}
    seen_event_ids: set[str] = set()

    @subscribe(PaymentSucceeded)
    def grant(event: PaymentSucceeded) -> None:
        if event.stripe_event_id in seen_event_ids:
            return
        seen_event_ids.add(event.stripe_event_id)
        granted_tiers[event.user_id] = event.tier

    original = PaymentSucceeded(
        user_id="u1",
        tier=Tier.DECISION_PACK,
        stripe_event_id="evt_abc",
    )
    replay = PaymentSucceeded(
        user_id="u1",
        tier=Tier.DECISION_PACK,
        stripe_event_id="evt_abc",
    )
    dispatch(original)
    dispatch(replay)

    assert granted_tiers == {"u1": "decision_pack"}
    assert len(seen_event_ids) == 1


def test_handlers_are_invoked_in_registration_order() -> None:
    order: list[str] = []

    @subscribe(PaymentSucceeded)
    def first(event: PaymentSucceeded) -> None:
        order.append("first")

    @subscribe(PaymentSucceeded)
    def second(event: PaymentSucceeded) -> None:
        order.append("second")

    dispatch(PaymentSucceeded(user_id="u1", tier=Tier.FREE, stripe_event_id="evt_1"))
    assert order == ["first", "second"]


def test_clear_subscribers_drops_all_registrations() -> None:
    received: list[PaymentSucceeded] = []

    @subscribe(PaymentSucceeded)
    def handler(event: PaymentSucceeded) -> None:
        received.append(event)

    clear_subscribers()
    dispatch(PaymentSucceeded(user_id="u1", tier=Tier.FREE, stripe_event_id="evt_1"))
    assert received == []


def test_event_payloads_are_immutable() -> None:
    """Frozen dataclasses prevent a buggy subscriber from mutating
    state visible to siblings — critical because the bus has no
    isolation layer between handlers."""
    event = PaymentSucceeded(user_id="u1", tier=Tier.FREE, stripe_event_id="evt_1")
    with pytest.raises(Exception):  # noqa: B017 — dataclasses raises FrozenInstanceError
        event.user_id = "u2"  # type: ignore[misc]


def test_event_id_defaults_to_unique_value() -> None:
    """Each event gets a fresh id by default so subscribers can
    dedupe across publish sites without coordinating with the
    publisher (only Stripe-style external ids need explicit values)."""
    a = ForecastCompleted(job_id="j1", user_id="u1", result_summary={})
    b = ForecastCompleted(job_id="j1", user_id="u1", result_summary={})
    assert a.event_id != b.event_id

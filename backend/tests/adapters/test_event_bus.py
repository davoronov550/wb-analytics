"""Adapter test for the in-process event bus (seam).

RED first: `shared.adapters.event_bus.InProcessEventBus` is.
Delivery is synchronous and by exact event type.
"""

from datetime import UTC, datetime

from shared.adapters.event_bus import InProcessEventBus
from shared.events import PriceChanged, ProductsCollected


def _collected(query: str = "наушники") -> ProductsCollected:
    return ProductsCollected(
        query=query,
        wb_ids=(1,),
        collected_count=1,
        occurred_at=datetime.now(UTC),
    )


class TestInProcessEventBus:
    def test_subscriber_receives_subscribed_event(self):
        bus = InProcessEventBus()
        received: list[ProductsCollected] = []
        bus.subscribe(ProductsCollected, received.append)

        event = _collected()
        bus.publish(event)

        assert received == [event]

    def test_multiple_subscribers_all_invoked(self):
        bus = InProcessEventBus()
        first: list[object] = []
        second: list[object] = []
        bus.subscribe(ProductsCollected, first.append)
        bus.subscribe(ProductsCollected, second.append)

        bus.publish(_collected())

        assert len(first) == 1
        assert len(second) == 1

    def test_only_matching_type_is_invoked(self):
        bus = InProcessEventBus()
        got: list[object] = []
        bus.subscribe(PriceChanged, got.append)

        bus.publish(_collected())  # a different event type

        assert got == []

    def test_publish_without_subscribers_is_noop(self):
        bus = InProcessEventBus()
        bus.publish(_collected())  # must not raise

    def test_handlers_invoked_synchronously_in_registration_order(self):
        bus = InProcessEventBus()
        order: list[str] = []
        bus.subscribe(ProductsCollected, lambda _e: order.append("first"))
        bus.subscribe(ProductsCollected, lambda _e: order.append("second"))

        bus.publish(_collected())

        assert order == ["first", "second"]

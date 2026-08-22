"""Microservices-seam test (T098) — EVENT_PUBLISHER selects the bus adapter.

Selecting a bus adapter is confined to shared.composition + the adapter; no
domain/application code changes (Constitution IV). Uses the pure factory so the
process-wide singleton is not mutated.
"""

from shared.adapters.event_bus import InProcessEventBus
from shared.adapters.message_bus import LoggingMessageBus
from shared.composition import create_event_bus


def test_default_mode_is_in_process():
    assert isinstance(create_event_bus("inprocess"), InProcessEventBus)


def test_bus_mode_selects_message_bus():
    assert isinstance(create_event_bus("bus"), LoggingMessageBus)


def test_message_bus_still_delivers_to_local_subscribers():
    bus = LoggingMessageBus()
    received = []
    from datetime import UTC, datetime

    from shared.events import ProductsCollected

    bus.subscribe(ProductsCollected, received.append)
    event = ProductsCollected(
        query="q", wb_ids=(1,), collected_count=1, occurred_at=datetime.now(UTC)
    )
    bus.publish(event)
    assert received == [event]

"""Message-bus event bus adapter (stand-in for Kafka/Rabbit/Redis Streams).

Demonstrates the microservices seam: selecting it (EVENT_PUBLISHER=bus) swaps the
in-process bus for one that would publish to an external broker — a change confined
to this adapter + the composition switch, with zero edits to domain/application
. Here it logs each published event (as if enqueued) and still
delivers to any locally-registered subscribers so a single-process run stays
functional.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from shared.application.ports import EventHandler
from shared.events import DomainEvent

logger = logging.getLogger("shared.bus")


class LoggingMessageBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        logger.info("→ message bus: %s %r", type(event).__name__, event)
        for handler in list(self._handlers.get(type(event), ())):
            handler(event)

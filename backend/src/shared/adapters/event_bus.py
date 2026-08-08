"""In-process synchronous event bus (implements EventBusPort).

The v1 cross-context seam: publishing an event invokes every handler subscribed
to its exact type, synchronously, in registration order. Swapping this for a
message-bus adapter (Kafka/Rabbit/Redis Streams) is the only change needed to
split contexts into services (Constitution IV).
"""

from __future__ import annotations

from collections import defaultdict

from shared.application.ports import EventHandler
from shared.events import DomainEvent


class InProcessEventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        # Copy so a handler that subscribes during dispatch doesn't affect this run.
        for handler in list(self._handlers.get(type(event), ())):
            handler(event)

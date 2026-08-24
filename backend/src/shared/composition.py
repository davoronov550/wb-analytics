"""Shared composition — process-wide singletons for the cross-context seam.

The event bus is a single instance so every context (catalog, analytics,
notifications, …) publishes to and subscribes on the same bus. The concrete bus is
chosen by EVENT_PUBLISHER (``inprocess`` | ``bus``): swapping it is confined to this
module + the bus adapter, with no domain/application changes.
Read from the environment (not Django settings) to keep the kernel framework-free.
"""

from __future__ import annotations

import os

from shared.adapters.clock import SystemClock
from shared.adapters.event_bus import InProcessEventBus
from shared.application.ports import ClockPort, EventBusPort


def create_event_bus(mode: str) -> EventBusPort:
    if mode == "bus":
        from shared.adapters.message_bus import LoggingMessageBus

        return LoggingMessageBus()
    return InProcessEventBus()


_event_bus: EventBusPort | None = None
_clock: ClockPort = SystemClock()


def get_event_bus() -> EventBusPort:
    global _event_bus
    if _event_bus is None:
        _event_bus = create_event_bus(os.environ.get("EVENT_PUBLISHER", "inprocess"))
    return _event_bus


def get_clock() -> ClockPort:
    return _clock

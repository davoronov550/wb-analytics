"""Shared composition — process-wide singletons for the in-process seam.

The event bus must be a single instance so every context (catalog, analytics,
notifications, …) publishes to and subscribes on the same bus. Each context's
composition root pulls these from here. Swapping the bus for a message-bus adapter
later is a change confined to this module.
"""

from __future__ import annotations

from shared.adapters.clock import SystemClock
from shared.adapters.event_bus import InProcessEventBus
from shared.application.ports import ClockPort, EventBusPort

_event_bus: EventBusPort = InProcessEventBus()
_clock: ClockPort = SystemClock()


def get_event_bus() -> EventBusPort:
    return _event_bus


def get_clock() -> ClockPort:
    return _clock

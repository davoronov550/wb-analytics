"""Shared kernel outbound ports.

Ports are structural interfaces (``typing.Protocol``) so adapters implement them
without importing this module. Concrete adapters live in ``shared/adapters`` and
are wired by each context's composition root.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from shared.events import DomainEvent

__all__ = ["EventBusPort", "EventHandler", "ClockPort", "TaskQueuePort"]

# A subscriber invoked with the published event.
EventHandler = Callable[[DomainEvent], None]


class EventBusPort(Protocol):
    """Publish/subscribe seam between bounded contexts."""

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Register ``handler`` to receive events of ``event_type``."""
        ...

    def publish(self, event: DomainEvent) -> None:
        """Deliver ``event`` to every handler subscribed to its type."""
        ...


class ClockPort(Protocol):
    """Time source — injected so use cases and tests are deterministic."""

    def now(self) -> datetime:
        """Return the current timezone-aware time."""
        ...


class TaskQueuePort(Protocol):
    """Enqueue background work off the request path."""

    def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        """Schedule a named task with a JSON-serializable payload; return its id."""
        ...

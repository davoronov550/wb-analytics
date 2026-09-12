"""Shared kernel outbound ports.

Ports are structural interfaces (``typing.Protocol``) so adapters implement them
without importing this module. Concrete adapters live in ``catalog/adapters/outbound`` and
are wired by each context's composition root.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from catalog.application.events import DomainEvent

__all__ = ["ClockPort", "EventBusPort", "EventHandler", "TaskQueuePort"]

# A subscriber invoked with the published event.
EventHandler = Callable[[DomainEvent], None]


class EventBusPort(Protocol):
    """Publish/subscribe seam between bounded contexts."""

    async def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Register ``handler`` to receive events of ``event_type``."""
        ...

    async def publish(self, event: DomainEvent) -> None:
        """Deliver ``event`` to every handler subscribed to its type."""
        ...


class ClockPort(Protocol):
    """Time source — injected so use cases and tests are deterministic.

    Единственный порт, оставшийся синхронным: чтение часов не ввод-вывод, и
    `await` перед ним сообщал бы читателю неправду о стоимости вызова."""

    def now(self) -> datetime:
        """Return the current timezone-aware time."""
        ...


class TaskQueuePort(Protocol):
    """Enqueue background work off the request path."""

    async def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        """Schedule a named task with a JSON-serializable payload; return its id."""
        ...

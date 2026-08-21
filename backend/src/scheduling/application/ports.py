"""Scheduling outbound ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from scheduling.domain.schedule import Schedule

__all__ = ["ScheduleRepositoryPort", "CollectionEnqueuerPort"]


class ScheduleRepositoryPort(Protocol):
    def create(
        self, *, query: str, spec: str, interval_seconds: int, active: bool, owner_id: int | None
    ) -> Schedule: ...

    def list_all(self, owner_id: int | None = None) -> list[Schedule]: ...

    def list_active(self) -> list[Schedule]: ...

    def get(self, schedule_id: int) -> Schedule | None: ...

    def set_active(self, schedule_id: int, active: bool) -> Schedule: ...

    def mark_ran(self, schedule_id: int, when: datetime) -> None: ...

    def delete(self, schedule_id: int) -> None: ...


class CollectionEnqueuerPort(Protocol):
    """Cross-context seam: enqueue a catalog collection run for a query."""

    def enqueue(self, query: str, max_pages: int | None = None) -> None: ...

"""ManageSchedules use case — CRUD over collection schedules."""

from __future__ import annotations

from scheduling.application.interval import parse_interval
from scheduling.application.ports import ScheduleRepositoryPort
from scheduling.domain.schedule import Schedule


class ManageSchedules:
    def __init__(self, *, repository: ScheduleRepositoryPort) -> None:
        self._repository = repository

    def create(
        self, *, query: str, spec: str, active: bool = True, owner_id: int | None = None
    ) -> Schedule:
        interval_seconds = parse_interval(spec)  # raises ValueError on bad input
        return self._repository.create(
            query=query.strip(),
            spec=spec.strip(),
            interval_seconds=interval_seconds,
            active=active,
            owner_id=owner_id,
        )

    def set_active(self, schedule_id: int, active: bool) -> Schedule:
        return self._repository.set_active(schedule_id, active)

    def delete(self, schedule_id: int) -> None:
        self._repository.delete(schedule_id)

    def list(self, owner_id: int | None = None) -> list[Schedule]:
        return self._repository.list_all(owner_id=owner_id)

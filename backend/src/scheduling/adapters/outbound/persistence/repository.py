"""Django implementation of ScheduleRepositoryPort (outbound adapter)."""

from __future__ import annotations

from datetime import datetime

from scheduling.adapters.outbound.persistence.models import ScheduleModel
from scheduling.domain.schedule import Schedule


def _to_dto(model: ScheduleModel) -> Schedule:
    return Schedule(
        id=model.id,
        query=model.query,
        spec=model.spec,
        interval_seconds=model.interval_seconds,
        active=model.active,
        owner_id=model.owner_id,
        last_run_at=model.last_run_at,
    )


class DjangoScheduleRepository:
    def create(
        self, *, query: str, spec: str, interval_seconds: int, active: bool, owner_id: int | None
    ) -> Schedule:
        row = ScheduleModel.objects.create(
            query=query,
            spec=spec,
            interval_seconds=interval_seconds,
            active=active,
            owner_id=owner_id,
        )
        return _to_dto(row)

    def list_all(self, owner_id: int | None = None) -> list[Schedule]:
        qs = ScheduleModel.objects.all()
        if owner_id is not None:
            qs = qs.filter(owner_id=owner_id)
        return [_to_dto(row) for row in qs.order_by("-created_at")]

    def list_active(self) -> list[Schedule]:
        return [_to_dto(row) for row in ScheduleModel.objects.filter(active=True)]

    def get(self, schedule_id: int) -> Schedule | None:
        row = ScheduleModel.objects.filter(pk=schedule_id).first()
        return _to_dto(row) if row else None

    def set_active(self, schedule_id: int, active: bool) -> Schedule:
        ScheduleModel.objects.filter(pk=schedule_id).update(active=active)
        return _to_dto(ScheduleModel.objects.get(pk=schedule_id))

    def mark_ran(self, schedule_id: int, when: datetime) -> None:
        ScheduleModel.objects.filter(pk=schedule_id).update(last_run_at=when)

    def delete(self, schedule_id: int) -> None:
        ScheduleModel.objects.filter(pk=schedule_id).delete()

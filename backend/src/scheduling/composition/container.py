"""Scheduling composition root."""

from __future__ import annotations

from scheduling.adapters.outbound.catalog_enqueuer import CatalogCollectionEnqueuer
from scheduling.adapters.outbound.persistence.repository import DjangoScheduleRepository
from scheduling.application.ports import ScheduleRepositoryPort
from scheduling.application.use_cases.manage_schedules import ManageSchedules
from scheduling.application.use_cases.run_due_schedules import RunDueSchedules
from shared.composition import get_clock


def build_schedule_repository() -> ScheduleRepositoryPort:
    return DjangoScheduleRepository()


def build_manage_schedules() -> ManageSchedules:
    return ManageSchedules(repository=build_schedule_repository())


def build_run_due_schedules() -> RunDueSchedules:
    return RunDueSchedules(
        repository=build_schedule_repository(),
        enqueuer=CatalogCollectionEnqueuer(),
        clock=get_clock(),
    )

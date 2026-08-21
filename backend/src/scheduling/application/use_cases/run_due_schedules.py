"""RunDueSchedules use case — enqueue collection for every due schedule (FE-01).

Invoked periodically by the Celery Beat adapter. Only active schedules whose
interval has elapsed since their last run are enqueued; each is then marked ran.
"""

from __future__ import annotations

from scheduling.application.ports import CollectionEnqueuerPort, ScheduleRepositoryPort
from shared.application.ports import ClockPort


class RunDueSchedules:
    def __init__(
        self,
        *,
        repository: ScheduleRepositoryPort,
        enqueuer: CollectionEnqueuerPort,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._enqueuer = enqueuer
        self._clock = clock

    def execute(self) -> int:
        now = self._clock.now()
        due = [s for s in self._repository.list_active() if s.is_due(now)]
        for schedule in due:
            self._enqueuer.enqueue(schedule.query)
            self._repository.mark_ran(schedule.id, now)
        return len(due)

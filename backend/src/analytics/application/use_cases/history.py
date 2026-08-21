"""History read + retention use cases (FE-04)."""

from __future__ import annotations

from datetime import datetime, timedelta

from analytics.application.ports import SnapshotRepositoryPort
from analytics.domain.snapshot import Snapshot
from shared.application.ports import ClockPort


class ListHistory:
    def __init__(self, *, repository: SnapshotRepositoryPort) -> None:
        self._repository = repository

    def execute(self, wb_id: int, since: datetime | None = None) -> list[Snapshot]:
        return self._repository.list(wb_id, since)


class ApplyRetention:
    def __init__(self, *, repository: SnapshotRepositoryPort, clock: ClockPort) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, retention_days: int) -> int:
        cutoff = self._clock.now() - timedelta(days=retention_days)
        return self._repository.delete_older_than(cutoff)

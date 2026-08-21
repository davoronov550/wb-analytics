"""EnqueueCollection use case — start an async collection run (FE-02).

Idempotent per query: if a job for the query is already pending/running, returns
it instead of enqueuing another (FR-022). Otherwise creates a pending job and
dispatches the background task via the queue port.
"""

from __future__ import annotations

from catalog.application.dto import ParseJob
from catalog.application.ports.outbound import ParseJobRepositoryPort
from shared.application.ports import TaskQueuePort

COLLECT_TASK_NAME = "catalog.collect_products"


class EnqueueCollection:
    def __init__(self, *, repository: ParseJobRepositoryPort, queue: TaskQueuePort) -> None:
        self._repository = repository
        self._queue = queue

    def execute(self, query: str, max_pages: int | None = None) -> ParseJob:
        active = self._repository.find_active(query)
        if active is not None:
            return active

        job = self._repository.create_pending(query)
        self._queue.enqueue(
            COLLECT_TASK_NAME,
            {"task_id": job.task_id, "query": query, "max_pages": max_pages},
        )
        return job

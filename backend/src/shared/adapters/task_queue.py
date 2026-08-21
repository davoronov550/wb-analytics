"""Celery task queue adapter (implements TaskQueuePort).

Dispatches a named Celery task with a JSON-serializable payload. In tests Celery
runs eagerly (CELERY_TASK_ALWAYS_EAGER), so no broker/worker is required.
"""

from __future__ import annotations


class CeleryTaskQueue:
    def __init__(self, app) -> None:
        self._app = app

    def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        result = self._app.send_task(task_name, kwargs=payload)
        return result.id

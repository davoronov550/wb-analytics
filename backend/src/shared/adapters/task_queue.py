"""Celery task queue adapter (implements TaskQueuePort).

Dispatches a named Celery task with a JSON-serializable payload. In tests Celery
runs eagerly (CELERY_TASK_ALWAYS_EAGER), so no broker/worker is required.
"""

from __future__ import annotations


class CeleryTaskQueue:
    def __init__(self, app) -> None:
        self._app = app

    def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        # Resolve the registered task and apply_async (honors task_always_eager,
        # unlike app.send_task, which always routes through the broker).
        task = self._app.tasks[task_name]
        result = task.apply_async(kwargs=payload)
        return result.id

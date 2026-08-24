"""Celery tasks for the catalog context (background collection).

The task is a thin driver over CollectProducts, updating the ParseJob status. It
records failures on the job instead of re-raising, so the HTTP `POST /api/parse/`
stays 202 and a worker does not crash-loop; the client observes `failed` via the
status endpoint.
"""

from __future__ import annotations

import logging

from celery import shared_task

from catalog.application.dto import CollectInput
from catalog.composition import container

logger = logging.getLogger("catalog")


@shared_task(name="catalog.collect_products")
def collect_products(task_id: str, query: str, max_pages: int | None = None) -> str:
    jobs = container.build_parse_job_repository()
    jobs.mark_running(task_id)
    try:
        result = container.build_collect_products().execute(
            CollectInput(query=query, max_pages=max_pages)
        )
        jobs.mark_done(task_id, created=result.created, updated=result.updated)
        return task_id
    except Exception as exc:  # noqa: BLE001 - record failure on the job, never crash the worker
        logger.warning("Collection task %s failed: %s", task_id, exc)
        jobs.mark_failed(task_id, str(exc))
        return task_id

"""Celery Beat task (inbound adapter) — periodically run due schedules.

Beat is configured (config/celery.py) to call this on a fixed cadence; the use
case decides which schedules are actually due.
"""

from __future__ import annotations

from celery import shared_task

from scheduling.composition import container


@shared_task(name="scheduling.run_due")
def run_due() -> int:
    return container.build_run_due_schedules().execute()

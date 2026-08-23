"""Pytest bootstrap for the backend.

Celery runs eagerly under pytest (settings enable task_always_eager when pytest is
imported), so tasks run inline with no broker/worker — Constitution II
(deterministic, offline tests).
"""
import os

os.environ.setdefault("EVENT_PUBLISHER", "inprocess")

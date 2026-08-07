"""Pytest bootstrap for the backend.

Runs at collection time (rootdir), before Django settings are imported by
pytest-django, so environment-driven settings pick up test-only values.
Celery runs eagerly in tests (no broker/worker needed) — Constitution II
(deterministic, offline tests).
"""
import os

os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("EVENT_PUBLISHER", "inprocess")

"""Celery application (async + scheduled work adapter — Constitution VII).

Task modules (`<context>/adapters/.../tasks.py`) are auto-discovered from
INSTALLED_APPS as they are added (T056/T057 for collection, T063 Beat schedule).
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("wb_analytics")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

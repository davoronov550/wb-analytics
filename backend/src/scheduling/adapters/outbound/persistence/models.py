"""Scheduling persistence models (Django ORM)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ScheduleModel(models.Model):
    """A periodic collection schedule for a query (FE-01)."""

    query = models.CharField(max_length=200)
    spec = models.CharField(max_length=50)
    interval_seconds = models.PositiveIntegerField()
    active = models.BooleanField(default=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "scheduling_schedule"

    def __str__(self) -> str:
        return f"{self.query} [{self.spec}]"

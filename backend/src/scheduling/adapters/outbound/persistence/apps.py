"""Django AppConfig for the scheduling persistence adapter."""

from __future__ import annotations

from django.apps import AppConfig


class SchedulingPersistenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scheduling.adapters.outbound.persistence"
    label = "scheduling"
    verbose_name = "Scheduling"

    def ready(self) -> None:
        # Register the Beat task (@shared_task) at startup.
        from scheduling.adapters.inbound.beat import tasks  # noqa: F401

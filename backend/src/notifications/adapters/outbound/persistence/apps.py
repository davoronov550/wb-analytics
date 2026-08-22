"""Django AppConfig for the notifications persistence adapter."""

from __future__ import annotations

from django.apps import AppConfig


class NotificationsPersistenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications.adapters.outbound.persistence"
    label = "notifications"
    verbose_name = "Notifications"

    def ready(self) -> None:
        # Subscribe the alert evaluator to collection/price-change events at startup.
        from notifications.composition import container

        container.register_subscribers()

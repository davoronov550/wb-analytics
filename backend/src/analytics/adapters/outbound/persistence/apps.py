"""Django AppConfig for the analytics persistence adapter."""

from __future__ import annotations

from django.apps import AppConfig


class AnalyticsPersistenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics.adapters.outbound.persistence"
    label = "analytics"
    verbose_name = "Analytics"

    def ready(self) -> None:
        # Wire the price-history recorder to the ProductsCollected event.
        from analytics.composition import container

        container.register_subscribers()

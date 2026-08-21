"""Django AppConfig for the catalog persistence adapter.

The persistence adapter is the Django "app" that owns the ORM models and
migrations. The domain and application packages are plain Python, not apps.
"""

from __future__ import annotations

from django.apps import AppConfig


class CatalogPersistenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog.adapters.outbound.persistence"
    label = "catalog"
    verbose_name = "Catalog"

    def ready(self) -> None:
        # Import the Celery tasks module so its @shared_task registers at startup
        # (needed for eager/worker dispatch by name).
        from catalog.adapters.outbound import tasks  # noqa: F401

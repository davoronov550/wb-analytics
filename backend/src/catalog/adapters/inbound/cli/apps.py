"""Django AppConfig for the catalog CLI adapter.

Registered as an app (with no models) only so Django discovers the management
commands under ``management/commands/``.
"""

from __future__ import annotations

from django.apps import AppConfig


class CatalogCliConfig(AppConfig):
    name = "catalog.adapters.inbound.cli"
    label = "catalog_cli"
    verbose_name = "Catalog CLI"

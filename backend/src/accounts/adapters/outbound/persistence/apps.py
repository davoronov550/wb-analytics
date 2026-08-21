"""Django AppConfig for the accounts persistence adapter."""

from __future__ import annotations

from django.apps import AppConfig


class AccountsPersistenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts.adapters.outbound.persistence"
    label = "accounts"
    verbose_name = "Accounts"

"""Accounts persistence models (Django ORM)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class SavedSearchModel(models.Model):
    """A user's saved query + filters (FE-09)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_searches"
    )
    name = models.CharField(max_length=200)
    query = models.CharField(max_length=200)
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_saved_search"

    def __str__(self) -> str:
        return f"{self.name} (owner {self.owner_id})"


class ExternalIdentityModel(models.Model):
    """A third-party identity (e.g. Google `sub`) linked to a local user (FE-09)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="identities"
    )
    provider = models.CharField(max_length=32)
    external_id = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_external_identity"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"], name="uniq_provider_external_id"
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.external_id} (user {self.user_id})"

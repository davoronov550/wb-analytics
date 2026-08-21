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

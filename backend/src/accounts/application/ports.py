"""Accounts outbound ports."""

from __future__ import annotations

from typing import Protocol

from accounts.application.dto import SavedSearch

__all__ = ["SavedSearchRepositoryPort"]


class SavedSearchRepositoryPort(Protocol):
    def create(self, *, owner_id: int, name: str, query: str, filters: dict) -> SavedSearch: ...

    def list(self, owner_id: int) -> list[SavedSearch]: ...

    def get(self, owner_id: int, saved_id: int) -> SavedSearch | None:
        """Owner-scoped lookup (None if missing or owned by someone else)."""
        ...

    def delete(self, owner_id: int, saved_id: int) -> bool:
        """Delete if owned by ``owner_id``; return whether a row was removed."""
        ...

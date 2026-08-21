"""ManageSavedSearches use case — owner-scoped CRUD (FE-09)."""

from __future__ import annotations

from accounts.application.dto import SavedSearch
from accounts.application.ports import SavedSearchRepositoryPort


class ManageSavedSearches:
    def __init__(self, *, repository: SavedSearchRepositoryPort) -> None:
        self._repository = repository

    def create(self, *, owner_id: int, name: str, query: str, filters: dict) -> SavedSearch:
        return self._repository.create(
            owner_id=owner_id, name=name.strip(), query=query.strip(), filters=filters or {}
        )

    def list(self, owner_id: int) -> list[SavedSearch]:
        return self._repository.list(owner_id)

    def delete(self, owner_id: int, saved_id: int) -> bool:
        return self._repository.delete(owner_id, saved_id)

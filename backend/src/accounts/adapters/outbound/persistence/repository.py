"""Django implementation of SavedSearchRepositoryPort (outbound adapter)."""

from __future__ import annotations

from accounts.adapters.outbound.persistence.models import SavedSearchModel
from accounts.application.dto import SavedSearch


def _to_dto(model: SavedSearchModel) -> SavedSearch:
    return SavedSearch(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        query=model.query,
        filters=model.filters or {},
    )


class DjangoSavedSearchRepository:
    def create(self, *, owner_id: int, name: str, query: str, filters: dict) -> SavedSearch:
        row = SavedSearchModel.objects.create(
            owner_id=owner_id, name=name, query=query, filters=filters
        )
        return _to_dto(row)

    def list(self, owner_id: int) -> list[SavedSearch]:
        return [
            _to_dto(row)
            for row in SavedSearchModel.objects.filter(owner_id=owner_id).order_by("-created_at")
        ]

    def get(self, owner_id: int, saved_id: int) -> SavedSearch | None:
        row = SavedSearchModel.objects.filter(pk=saved_id, owner_id=owner_id).first()
        return _to_dto(row) if row else None

    def delete(self, owner_id: int, saved_id: int) -> bool:
        deleted, _ = SavedSearchModel.objects.filter(pk=saved_id, owner_id=owner_id).delete()
        return deleted > 0

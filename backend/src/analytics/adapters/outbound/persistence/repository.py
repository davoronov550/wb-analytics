"""Django implementation of SnapshotRepositoryPort (outbound adapter)."""

from __future__ import annotations

from datetime import datetime

from analytics.adapters.outbound.persistence.models import SnapshotModel
from analytics.domain.snapshot import Snapshot


def _to_dto(model: SnapshotModel) -> Snapshot:
    return Snapshot(
        wb_id=model.wb_id,
        price=model.price,
        sale_price=model.sale_price,
        rating=model.rating,
        captured_at=model.captured_at,
    )


class DjangoSnapshotRepository:
    def add(self, snapshot: Snapshot) -> None:
        SnapshotModel.objects.create(
            wb_id=snapshot.wb_id,
            price=snapshot.price,
            sale_price=snapshot.sale_price,
            rating=snapshot.rating,
            captured_at=snapshot.captured_at,
        )

    def last(self, wb_id: int) -> Snapshot | None:
        row = SnapshotModel.objects.filter(wb_id=wb_id).order_by("-captured_at").first()
        return _to_dto(row) if row else None

    def list(self, wb_id: int, since: datetime | None = None) -> list[Snapshot]:
        qs = SnapshotModel.objects.filter(wb_id=wb_id)
        if since is not None:
            qs = qs.filter(captured_at__gte=since)
        return [_to_dto(row) for row in qs.order_by("captured_at")]

    def delete_older_than(self, cutoff: datetime) -> int:
        deleted, _ = SnapshotModel.objects.filter(captured_at__lt=cutoff).delete()
        return deleted

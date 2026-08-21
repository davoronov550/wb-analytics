"""Analytics outbound ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from analytics.application.dto import SnapshotInput
from analytics.domain.snapshot import Snapshot

__all__ = ["SnapshotRepositoryPort", "ProductReaderPort"]


class SnapshotRepositoryPort(Protocol):
    def add(self, snapshot: Snapshot) -> None: ...

    def last(self, wb_id: int) -> Snapshot | None:
        """The most recent snapshot for a product, if any."""
        ...

    def list(self, wb_id: int, since: datetime | None = None) -> list[Snapshot]:
        """Snapshots for a product in chronological order."""
        ...

    def delete_older_than(self, cutoff: datetime) -> int:
        """Delete snapshots captured before ``cutoff``; return how many were removed."""
        ...


class ProductReaderPort(Protocol):
    """Read current product figures from the catalog (cross-context seam)."""

    def snapshot_inputs(self, wb_ids: list[int]) -> list[SnapshotInput]: ...

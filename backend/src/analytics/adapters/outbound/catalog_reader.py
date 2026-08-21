"""ProductReaderPort implementation — read current product figures from catalog.

The analytics→catalog seam for snapshotting: reads the catalog's stored products
by wb_id. Confined to this adapter (an edge), not the analytics use cases.
"""

from __future__ import annotations

from analytics.application.dto import SnapshotInput
from catalog.adapters.outbound.persistence.models import ProductModel


class CatalogProductReader:
    def snapshot_inputs(self, wb_ids: list[int]) -> list[SnapshotInput]:
        rows = ProductModel.objects.filter(wb_id__in=wb_ids).values(
            "wb_id", "price", "sale_price", "rating"
        )
        return [
            SnapshotInput(
                wb_id=row["wb_id"],
                price=row["price"],
                sale_price=row["sale_price"],
                rating=row["rating"],
            )
            for row in rows
        ]

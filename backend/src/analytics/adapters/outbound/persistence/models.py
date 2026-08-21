"""Analytics persistence models (Django ORM) — append-only price history."""

from __future__ import annotations

from django.db import models


class SnapshotModel(models.Model):
    """One price/rating snapshot for a product at a point in time (FE-04)."""

    wb_id = models.BigIntegerField(db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    captured_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "analytics_snapshot"
        indexes = [models.Index(fields=["wb_id", "captured_at"])]

    def __str__(self) -> str:
        return f"{self.wb_id} @ {self.captured_at.isoformat()}"

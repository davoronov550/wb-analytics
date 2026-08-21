"""Catalog persistence models (Django ORM) — the ONLY place ORM exists for this
context. Mapped to/from the domain in ``mappers.py``; the domain never sees these.
"""

from __future__ import annotations

from django.db import models


class SearchQueryModel(models.Model):
    """A query/category a collection run was performed for."""

    text = models.CharField(max_length=200, db_index=True)
    collected_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "catalog_search_query"

    def __str__(self) -> str:
        return self.text


class ProductModel(models.Model):
    """A Wildberries product; ``wb_id`` is the idempotent upsert key (FR-004)."""

    wb_id = models.BigIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=512)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    reviews_count = models.PositiveIntegerField(default=0)
    source_query = models.ForeignKey(
        SearchQueryModel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_product"
        indexes = [
            models.Index(fields=["price"]),
            models.Index(fields=["sale_price"]),
            models.Index(fields=["rating"]),
            models.Index(fields=["reviews_count"]),
        ]

    def __str__(self) -> str:
        return f"{self.wb_id} {self.name}"


class ParseJobModel(models.Model):
    """Status of an asynchronous collection run (FE-02)."""

    task_id = models.CharField(primary_key=True, max_length=64)
    query = models.CharField(max_length=200, db_index=True)
    status = models.CharField(max_length=16, default="pending", db_index=True)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "catalog_parse_job"
        indexes = [models.Index(fields=["query", "status"])]

    def __str__(self) -> str:
        return f"{self.task_id} {self.query} [{self.status}]"

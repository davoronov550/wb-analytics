"""E2E tests (T088) for GET /api/export/ (FE-08) — need the DB (@django_db)."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def _p(wb_id, price, sale, rating, reviews, name):
    return Product.create(
        wb_id=wb_id,
        name=name,
        price=Money(Decimal(price)),
        sale_price=Money(Decimal(sale)),
        rating=Rating(Decimal(rating)),
        reviews_count=ReviewsCount(reviews),
        source_query="наушники",
    )


@pytest.mark.django_db
def test_export_csv_matches_filter():
    DjangoProductRepository().upsert_many(
        [_p(1, "100", "50", "4.8", 500, "A"), _p(2, "200", "150", "4.2", 50, "B")],
        "наушники",
    )
    resp = APIClient().get("/api/export/?min_price=100&format=csv")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    body = b"".join(resp.streaming_content).decode("utf-8")
    lines = body.strip().splitlines()
    assert lines[0].startswith("wb_id")
    assert len(lines) == 2  # header + only wb 2 (sale 150 ≥ 100)
    assert lines[1].startswith("2,")


@pytest.mark.django_db
def test_export_xlsx_content_type():
    DjangoProductRepository().upsert_many([_p(1, "100", "50", "4.0", 10, "A")], "наушники")
    resp = APIClient().get("/api/export/?format=xlsx")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
    assert resp.content[:2] == b"PK"  # XLSX is a zip container

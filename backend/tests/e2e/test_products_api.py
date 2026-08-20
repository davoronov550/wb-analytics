"""E2E tests (T032) for GET /api/products/ — REQUIRE PostgreSQL + the view (T038).

Marked ``django_db``; run once a database is available:
    docker compose up -d db
    .venv/Scripts/python -m pytest tests/e2e/test_products_api.py

Covers filtering (price on sale_price, rating, reviews), ordering, discount fields
in the payload, and 400 on invalid input (FR-007/08/09, SC-005).
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount

pytestmark = pytest.mark.django_db


def _seed():
    DjangoProductRepository().upsert_many(
        [
            _p(1, "100", "50", "4.8", 500, "A"),
            _p(2, "200", "150", "4.2", 50, "B"),
            _p(3, "300", "300", "3.5", 1000, "C"),
        ],
        "наушники",
    )


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


def test_lists_all_products():
    _seed()
    resp = APIClient().get("/api/products/")
    assert resp.status_code == 200
    assert resp.data["count"] == 3


def test_min_price_filters_on_sale_price_with_ordering():
    _seed()
    resp = APIClient().get("/api/products/?min_price=100&ordering=sale_price")
    assert resp.status_code == 200
    assert [r["wb_id"] for r in resp.data["results"]] == [2, 3]


def test_min_rating_and_min_reviews():
    _seed()
    resp = APIClient().get("/api/products/?min_rating=4&min_reviews=100")
    assert [r["wb_id"] for r in resp.data["results"]] == [1]


def test_payload_includes_discount_fields():
    _seed()
    resp = APIClient().get("/api/products/?ordering=price")
    first = resp.data["results"][0]
    assert first["wb_id"] == 1
    assert first["discount_abs"] == "50.00"
    assert "discount_pct" in first


def test_invalid_rating_returns_400():
    resp = APIClient().get("/api/products/?min_rating=9")
    assert resp.status_code == 400

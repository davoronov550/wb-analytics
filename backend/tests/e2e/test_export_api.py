"""E2E tests for GET /api/export/ — need the DB (@django_db).

Export dumps the whole filtered catalogue, so it is an authenticated-only,
throttled operation.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import caches
from rest_framework.test import APIClient

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    caches["default"].clear()
    yield
    caches["default"].clear()


def auth_client() -> APIClient:
    user = User.objects.create_user(username="exporter", password="pw-abcdefgh")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


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
    resp = auth_client().get("/api/export/?min_price=100&format=csv")
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
    resp = auth_client().get("/api/export/?format=xlsx")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
    assert resp.content[:2] == b"PK"  # XLSX is a zip container


@pytest.mark.django_db
def test_export_requires_authentication():
    """Anonymous callers must not be able to dump the catalogue."""
    resp = APIClient().get("/api/export/?format=csv")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_export_is_throttled():
    client = auth_client()
    statuses = [client.get("/api/export/?format=csv").status_code for _ in range(15)]
    assert 429 in statuses, f"export flood was not throttled: {statuses}"


@pytest.mark.django_db
def test_invalid_filter_still_returns_400_not_404():
    """Regression: `format` must stay a plain query param, not DRF negotiation."""
    resp = auth_client().get("/api/export/?min_rating=abc&format=csv")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_unknown_format_falls_back_to_csv():
    DjangoProductRepository().upsert_many([_p(1, "100", "50", "4.0", 10, "A")], "наушники")
    resp = auth_client().get("/api/export/?format=weird")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")

"""E2E tests for GET /api/stats/.

Invalid-param 400 runs offline; aggregation correctness needs PostgreSQL
(PERCENTILE_CONT median) — @django_db, deferred.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def test_invalid_param_returns_400():
    resp = APIClient().get("/api/stats/?min_rating=9")
    assert resp.status_code == 400


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
def test_stats_aggregates_over_filtered_set():
    DjangoProductRepository().upsert_many(
        [
            _p(1, "100", "100", "4.0", 10, "A"),  # no discount
            _p(2, "200", "100", "4.5", 500, "B"),  # discount 100
            _p(3, "300", "150", "4.8", 50, "C"),  # discount 150
        ],
        "наушники",
    )

    resp = APIClient().get("/api/stats/")
    assert resp.status_code == 200
    data = resp.data
    assert data["count"] == 3
    assert data["avg_price"] == "116.67"  # avg sale_price of 100/100/150
    assert data["median_price"] == "100.00"
    assert data["discount_share"] == pytest.approx(0.6667, abs=1e-3)
    assert data["top_by_reviews"][0]["wb_id"] == 2  # 500 reviews


@pytest.mark.django_db
def test_stats_comparison_with_repeated_query_param():
    DjangoProductRepository().upsert_many([_p(1, "100", "80", "4.5", 10, "A")], "наушники")
    DjangoProductRepository().upsert_many([_p(2, "200", "150", "4.0", 20, "B")], "чайники")

    resp = APIClient().get("/api/stats/?query=наушники&query=чайники")
    assert resp.status_code == 200
    items = resp.data["items"]
    assert [i["query"] for i in items] == ["наушники", "чайники"]
    assert items[0]["stats"]["count"] == 1
    assert items[1]["stats"]["count"] == 1

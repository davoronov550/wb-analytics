"""Integration tests (T018) for DjangoProductRepository — REQUIRE PostgreSQL.

Marked ``django_db``; run once a database is available:
    docker compose up -d db
    .venv/Scripts/python -m pytest tests/adapters/test_product_repository.py

Covers upsert idempotency by wb_id and list filter/order/pagination (FR-004/07/08).
"""

from decimal import Decimal

import pytest

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.application.dto import Ordering, ProductFilter
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount

pytestmark = pytest.mark.django_db


def _p(wb_id, price, sale, rating, reviews, name="x") -> Product:
    return Product.create(
        wb_id=wb_id,
        name=name,
        price=Money(Decimal(price)),
        sale_price=Money(Decimal(sale)),
        rating=Rating(Decimal(rating)),
        reviews_count=ReviewsCount(reviews),
        source_query="наушники",
    )


class TestUpsert:
    def test_insert_then_update_without_duplicates(self):
        repo = DjangoProductRepository()

        first = repo.upsert_many([_p(1, "100", "80", "4.5", 10)], "наушники")
        assert (first.created, first.updated) == (1, 0)

        second = repo.upsert_many([_p(1, "100", "60", "4.6", 12)], "наушники")
        assert (second.created, second.updated) == (0, 1)

        page = repo.list(ProductFilter(), Ordering(field="price"), 1, 100)
        assert page.count == 1
        assert page.items[0].sale_price == Money(Decimal("60.00"))


class TestList:
    def _seed(self, repo: DjangoProductRepository) -> None:
        repo.upsert_many(
            [
                _p(1, "100", "50", "4.8", 500, "A"),
                _p(2, "200", "150", "4.2", 50, "B"),
                _p(3, "300", "300", "3.5", 1000, "C"),
            ],
            "наушники",
        )

    def test_filter_min_price_applies_to_sale_price(self):
        repo = DjangoProductRepository()
        self._seed(repo)
        page = repo.list(
            ProductFilter(min_price=Decimal("100")),
            Ordering(field="sale_price", descending=False),
            1,
            100,
        )
        assert [p.wb_id for p in page.items] == [2, 3]

    def test_filter_min_rating_and_min_reviews(self):
        repo = DjangoProductRepository()
        self._seed(repo)
        page = repo.list(
            ProductFilter(min_rating=Decimal("4.0"), min_reviews=100),
            Ordering(field="rating"),
            1,
            100,
        )
        assert [p.wb_id for p in page.items] == [1]

    def test_filter_rating_range_applies_both_bounds(self):
        repo = DjangoProductRepository()
        self._seed(repo)  # ratings: #1=4.8, #2=4.2, #3=3.5
        page = repo.list(
            ProductFilter(min_rating=Decimal("4.0"), max_rating=Decimal("4.5")),
            Ordering(field="rating"),
            1,
            100,
        )
        assert [p.wb_id for p in page.items] == [2]

    def test_filter_reviews_range_applies_both_bounds(self):
        repo = DjangoProductRepository()
        self._seed(repo)  # reviews: #1=500, #2=50, #3=1000
        page = repo.list(
            ProductFilter(min_reviews=100, max_reviews=800),
            Ordering(field="reviews_count"),
            1,
            100,
        )
        assert [p.wb_id for p in page.items] == [1]

    def test_ordering_ascending_and_descending(self):
        repo = DjangoProductRepository()
        self._seed(repo)
        asc = repo.list(ProductFilter(), Ordering(field="price", descending=False), 1, 100)
        assert [p.wb_id for p in asc.items] == [1, 2, 3]
        desc = repo.list(ProductFilter(), Ordering(field="price", descending=True), 1, 100)
        assert [p.wb_id for p in desc.items] == [3, 2, 1]

    def test_pagination(self):
        repo = DjangoProductRepository()
        self._seed(repo)
        page1 = repo.list(ProductFilter(), Ordering(field="price", descending=False), 1, 2)
        assert page1.count == 3
        assert [p.wb_id for p in page1.items] == [1, 2]
        page2 = repo.list(ProductFilter(), Ordering(field="price", descending=False), 2, 2)
        assert [p.wb_id for p in page2.items] == [3]

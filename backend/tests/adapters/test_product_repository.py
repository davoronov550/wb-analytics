"""Integration tests for DjangoProductRepository — REQUIRE PostgreSQL.

Marked ``django_db``; run once a database is available:
    docker compose up -d db
    .venv/Scripts/python -m pytest tests/adapters/test_product_repository.py

Covers upsert idempotency by wb_id and list filter/order/pagination.
"""

from decimal import Decimal

import pytest

from catalog.adapters.outbound.persistence.mappers import to_defaults
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

    def test_mixed_batch_splits_created_and_updated(self):
        """A real collection is mostly re-seen products with a few new ones.

        The created/updated split is not cosmetic: it feeds the CLI summary,
        ParseJob.mark_done() and GET /api/tasks/{id}/, so a bulk upsert must
        keep reporting it exactly.
        """
        repo = DjangoProductRepository()
        repo.upsert_many(
            [_p(1, "100", "80", "4.5", 10), _p(2, "200", "150", "4.0", 20)], "наушники"
        )

        result = repo.upsert_many(
            [
                _p(1, "110", "90", "4.6", 11),  # existing
                _p(2, "210", "160", "4.1", 21),  # existing
                _p(3, "300", "250", "4.7", 30),  # new
                _p(4, "400", "350", "4.8", 40),  # new
            ],
            "наушники",
        )

        assert (result.created, result.updated) == (2, 2)
        page = repo.list(ProductFilter(), Ordering(field="price"), 1, 100)
        assert page.count == 4

    def test_updates_overwrite_every_mutable_column(self):
        repo = DjangoProductRepository()
        repo.upsert_many([_p(1, "100", "80", "4.5", 10, "old name")], "наушники")
        repo.upsert_many([_p(1, "999", "555", "3.1", 77, "new name")], "наушники")

        page = repo.list(ProductFilter(), Ordering(field="price"), 1, 100)
        item = page.items[0]
        assert item.name == "new name"
        assert item.price == Money(Decimal("999.00"))
        assert item.sale_price == Money(Decimal("555.00"))
        assert item.rating == Rating(Decimal("3.1"))
        assert item.reviews_count == ReviewsCount(77)

    def test_upsert_is_batched_not_one_query_per_product(self):
        """Guards the fix: the old loop issued ~2 queries per product."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        repo = DjangoProductRepository()
        products = [_p(i, "100", "80", "4.5", 10) for i in range(1, 31)]

        with CaptureQueriesContext(connection) as ctx:
            repo.upsert_many(products, "наушники")

        assert len(ctx) < 15, f"30 products should not need {len(ctx)} queries"

    def test_failure_midway_leaves_no_partial_write(self):
        """The whole batch commits or none of it does.

        The failure is injected *after* some rows would already be mapped, so a
        non-transactional implementation would leave half the batch behind.
        """
        from unittest.mock import patch

        repo = DjangoProductRepository()
        repo.upsert_many([_p(1, "100", "80", "4.5", 10)], "наушники")

        calls = {"n": 0}
        real = to_defaults

        def explode_on_third(product):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("boom")
            return real(product)

        target = "catalog.adapters.outbound.persistence.repository.to_defaults"
        with patch(target, side_effect=explode_on_third):
            with pytest.raises(RuntimeError):
                repo.upsert_many(
                    [
                        _p(2, "200", "150", "4.0", 20),
                        _p(3, "300", "250", "4.1", 30),
                        _p(4, "400", "350", "4.2", 40),
                    ],
                    "наушники",
                )

        page = repo.list(ProductFilter(), Ordering(field="price"), 1, 100)
        assert [p.wb_id for p in page.items] == [1], "the failed batch must not persist"


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

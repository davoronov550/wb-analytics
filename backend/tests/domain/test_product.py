"""Domain tests for the catalog Product entity (pure)."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def _make(**overrides) -> Product:
    base = dict(
        wb_id=1,
        name="Наушники",
        price=Money(Decimal("100.00")),
        sale_price=Money(Decimal("60.00")),
        rating=Rating(Decimal("4.5")),
        reviews_count=ReviewsCount(100),
        source_query="наушники",
    )
    base.update(overrides)
    return Product.create(**base)


class TestProductCreate:
    def test_valid_product(self):
        p = _make()
        assert p.wb_id == 1
        assert p.name == "Наушники"
        assert p.price == Money(Decimal("100.00"))

    def test_trims_name(self):
        assert _make(name="  Наушники  ").name == "Наушники"

    def test_blank_name_raises(self):
        with pytest.raises(ValueError):
            _make(name="   ")

    def test_nonpositive_wb_id_raises(self):
        with pytest.raises(ValueError):
            _make(wb_id=0)

    def test_clamps_sale_price_above_price(self):
        p = _make(price=Money(Decimal("50.00")), sale_price=Money(Decimal("80.00")))
        assert p.sale_price == Money(Decimal("50.00"))

    def test_keeps_sale_price_at_or_below_price(self):
        p = _make(price=Money(Decimal("100.00")), sale_price=Money(Decimal("60.00")))
        assert p.sale_price == Money(Decimal("60.00"))

    def test_is_immutable(self):
        p = _make()
        with pytest.raises(FrozenInstanceError):
            p.name = "x"  # type: ignore[misc]


class TestProductRehydrate:
    def test_rehydrate_builds_exact_values(self):
        p = Product.rehydrate(
            wb_id=5,
            name="A",
            price=Money(Decimal("10.00")),
            sale_price=Money(Decimal("9.00")),
            rating=Rating(Decimal("3.0")),
            reviews_count=ReviewsCount(2),
            source_query=None,
        )
        assert p.wb_id == 5
        assert p.source_query is None
        assert p.sale_price == Money(Decimal("9.00"))

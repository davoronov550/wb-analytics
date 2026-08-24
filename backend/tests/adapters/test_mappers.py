"""Mapper tests — pure ORM<->domain mapping, no DB access.

These construct model instances in memory (no .save / no query), so they run
without a database.
"""

from decimal import Decimal

from catalog.adapters.outbound.persistence.mappers import to_defaults, to_domain
from catalog.adapters.outbound.persistence.models import ProductModel
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def test_to_domain_from_model_without_query():
    model = ProductModel(
        wb_id=7,
        name="Наушники",
        price=Decimal("100.00"),
        sale_price=Decimal("60.00"),
        rating=Decimal("4.5"),
        reviews_count=12,
        source_query=None,
    )
    product = to_domain(model)
    assert product.wb_id == 7
    assert product.name == "Наушники"
    assert product.price == Money(Decimal("100.00"))
    assert product.sale_price == Money(Decimal("60.00"))
    assert product.rating == Rating(Decimal("4.5"))
    assert product.reviews_count == ReviewsCount(12)
    assert product.source_query is None


def test_to_defaults_maps_value_objects_to_columns():
    product = Product.create(
        wb_id=1,
        name="x",
        price=Money(Decimal("50.00")),
        sale_price=Money(Decimal("40.00")),
        rating=Rating(Decimal("3.0")),
        reviews_count=ReviewsCount(5),
        source_query="q",
    )
    assert to_defaults(product) == {
        "name": "x",
        "price": Decimal("50.00"),
        "sale_price": Decimal("40.00"),
        "rating": Decimal("3.0"),
        "reviews_count": 5,
    }


def test_round_trip_defaults_then_domain():
    product = Product.create(
        wb_id=9,
        name="Item",
        price=Money(Decimal("200.00")),
        sale_price=Money(Decimal("150.00")),
        rating=Rating(Decimal("4.0")),
        reviews_count=ReviewsCount(3),
        source_query="q",
    )
    model = ProductModel(wb_id=product.wb_id, source_query=None, **to_defaults(product))
    back = to_domain(model)
    assert back.wb_id == product.wb_id
    assert back.price == product.price
    assert back.sale_price == product.sale_price
    assert back.rating == product.rating
    assert back.reviews_count == product.reviews_count

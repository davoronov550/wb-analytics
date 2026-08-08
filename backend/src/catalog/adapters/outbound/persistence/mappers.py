"""Mapping between ORM rows and the domain Product (kept out of the domain).

``to_domain`` rebuilds a domain entity from a stored row; ``to_defaults`` yields
the column values for an upsert (the ``source_query`` FK is set by the repository).
"""

from __future__ import annotations

from catalog.adapters.outbound.persistence.models import ProductModel
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def to_domain(model: ProductModel) -> Product:
    source_query = model.source_query.text if model.source_query_id else None
    return Product.rehydrate(
        wb_id=model.wb_id,
        name=model.name,
        price=Money(model.price),
        sale_price=Money(model.sale_price),
        rating=Rating(model.rating),
        reviews_count=ReviewsCount(model.reviews_count),
        source_query=source_query,
    )


def to_defaults(product: Product) -> dict:
    """Column values for ``update_or_create(defaults=...)`` (excludes wb_id/FK)."""
    return {
        "name": product.name,
        "price": product.price.amount,
        "sale_price": product.sale_price.amount,
        "rating": product.rating.value,
        "reviews_count": product.reviews_count.value,
    }

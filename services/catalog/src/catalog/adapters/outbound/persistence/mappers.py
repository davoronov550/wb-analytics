"""Перевод между строками таблицы и доменным Product.

Живёт в адаптере, а не в домене: домен не должен знать, что его вообще
где-то хранят. Скопирован из Django-версии с заменой модели ORM на строку
SQLAlchemy — правила отображения те же, потому что и схема та же.
"""

from __future__ import annotations

from typing import Any

from catalog.adapters.outbound.persistence.models import ProductRow
from catalog.domain.product import Product
from catalog.domain.value_objects import Money, Rating, ReviewsCount

__all__ = ["to_domain", "to_row_values"]


def to_domain(row: ProductRow, source_query: str | None) -> Product:
    """Строка → доменный Product.

    `rehydrate`, а не `create`: инварианты уже проверены при записи, а
    повторная проверка отвергла бы строку, которая легально лежит в базе с тех
    пор, как правило было мягче.

    `source_query` передаётся отдельно, а не читается через `row.source_query`:
    ленивая загрузка отношения на каждую строку — это N+1 на странице в тысячу
    товаров, ровно тот дефект, который миграция и должна убрать.
    """
    return Product.rehydrate(
        wb_id=row.wb_id,
        name=row.name,
        price=Money(row.price),
        sale_price=Money(row.sale_price),
        rating=Rating(row.rating),
        reviews_count=ReviewsCount(row.reviews_count),
        source_query=source_query,
    )


def to_row_values(product: Product) -> dict[str, Any]:
    """Значения колонок для upsert. Без `wb_id` и внешнего ключа — их ставит
    репозиторий, и без `created_at`: повторно увиденный товар сохраняет
    исходное время создания."""
    return {
        "name": product.name,
        "price": product.price.amount,
        "sale_price": product.sale_price.amount,
        "rating": product.rating.value,
        "reviews_count": product.reviews_count.value,
    }

"""Схемы ответа `GET /v1/products` (T130).

Задача — не «сериализовать товар», а отдать ровно те байты, что отдаёт Django:
на время канареечного вывода (T143) один и тот же запрос уходит то в одну
реализацию, то в другую, и различие в ответе клиент увидит как мерцание данных.

Что здесь воспроизводится дословно, потому что иначе не совпадёт:

* **Десятичные — строки, а не числа.** DRF при `COERCE_DECIMAL_TO_STRING`
  (умолчание) отдаёт `"2600.00"`, а не `2600.0`. Число потеряло бы хвостовые
  нули и, на больших значениях, точность.
* **Фиксированная точность.** У цены и скидки два знака, у рейтинга один:
  `"4.0"`, а не `"4"`. Домен уже квантует значения, но квантование повторено
  здесь явно — сериализация не должна зависеть от того, что кто-то выше по
  стеку не забыл.
* **Порядок ключей** — как в `ProductViewSerializer`. JSON-объекты
  неупорядочены по стандарту, но побайтовое сравнение этого не знает.

Компактные разделители и `ensure_ascii=False` даёт `JSONResponse` Starlette —
совпадает с рендерером DRF, специально ничего делать не нужно.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer

__all__ = ["ProductPageSchema", "ProductViewSchema"]

_MONEY = Decimal("0.01")
_RATING = Decimal("0.1")


class ProductViewSchema(BaseModel):
    """Товар в выдаче. Поля в порядке `ProductViewSerializer`."""

    model_config = ConfigDict(frozen=True)

    wb_id: int
    name: str
    price: Decimal
    sale_price: Decimal
    discount_abs: Decimal
    discount_pct: Decimal
    rating: Decimal
    reviews_count: int
    query: str | None
    updated_at: datetime | None

    @field_serializer("price", "sale_price", "discount_abs", "discount_pct")
    def _money(self, value: Decimal) -> str:
        return str(value.quantize(_MONEY))

    @field_serializer("rating")
    def _rating(self, value: Decimal) -> str:
        return str(value.quantize(_RATING))


class ProductPageSchema(BaseModel):
    """Конверт страницы DRF.

    `next` и `previous` всегда `null`: Django собирает конверт вручную и ссылок
    не выдаёт. Повторяется как есть — поля исчезнут вместе с переходом на
    курсор (T152), а не раньше.
    """

    model_config = ConfigDict(frozen=True)

    count: int
    next: str | None = None
    previous: str | None = None
    results: tuple[ProductViewSchema, ...]

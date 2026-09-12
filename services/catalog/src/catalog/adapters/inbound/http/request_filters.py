"""Разбор параметров запроса в DTO прикладного слоя (T130).

Перенесено из `catalog/adapters/inbound/http/request_filters.py` Django с одним
содержательным изменением: сортировка читается списком, а не одним полем
(T110). Остальное повторяется дословно, включая границы и тексты ошибок —
на канареечном выводе оба сервиса отвечают на один и тот же запрос, и
расхождение в валидации видно клиенту как отказ там, где раньше был ответ.

Разбор руками, а не через `Query(...)` FastAPI: у части параметров правила
перекрёстные (`min_rating <= max_rating`), а у `sort` — собственный формат,
и объявить это декларативно всё равно не получится. Одно место вместо двух.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from catalog.application.dto import ORDERABLE_FIELDS, Ordering, ProductFilter, SortKey
from catalog.application.errors import InvalidFilter

__all__ = ["MAX_PAGE_SIZE", "parse_ordering", "parse_pagination", "parse_product_filter"]

#: Предел строк на страницу. Как в Django: значение выше молча обрезается, а не
#: отвергается — поведение видно клиенту и меняться в T130 не должно.
MAX_PAGE_SIZE = 1000

#: Сколько уровней сортировки принимается. Интерфейс предлагает пять полей, и
#: список длиннее — либо ошибка клиента, либо попытка нагрузить планировщик.
MAX_SORT_KEYS = len(ORDERABLE_FIELDS)


def _decimal(params: Mapping[str, str], key: str) -> Decimal | None:
    raw = params.get(key)
    if raw is None or raw == "":
        return None
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidFilter(f"{key} must be a number") from exc


def _int(params: Mapping[str, str], key: str) -> int | None:
    raw = params.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidFilter(f"{key} must be an integer") from exc


def parse_product_filter(params: Mapping[str, str]) -> ProductFilter:
    """Фильтры. Тексты ошибок — как в Django, дословно."""
    min_price = _decimal(params, "min_price")
    max_price = _decimal(params, "max_price")
    min_rating = _decimal(params, "min_rating")
    max_rating = _decimal(params, "max_rating")
    min_reviews = _int(params, "min_reviews")
    max_reviews = _int(params, "max_reviews")

    if min_price is not None and min_price < 0:
        raise InvalidFilter("min_price must be >= 0")
    if max_price is not None and max_price < 0:
        raise InvalidFilter("max_price must be >= 0")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise InvalidFilter("min_price must be <= max_price")
    for key, value in (("min_rating", min_rating), ("max_rating", max_rating)):
        if value is not None and not (Decimal("0") <= value <= Decimal("5")):
            raise InvalidFilter(f"{key} must be within [0, 5]")
    if min_rating is not None and max_rating is not None and min_rating > max_rating:
        raise InvalidFilter("min_rating must be <= max_rating")
    if min_reviews is not None and min_reviews < 0:
        raise InvalidFilter("min_reviews must be >= 0")
    if max_reviews is not None and max_reviews < 0:
        raise InvalidFilter("max_reviews must be >= 0")
    if min_reviews is not None and max_reviews is not None and min_reviews > max_reviews:
        raise InvalidFilter("min_reviews must be <= max_reviews")

    return ProductFilter(
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        max_rating=max_rating,
        min_reviews=min_reviews,
        max_reviews=max_reviews,
        query=params.get("query") or None,
    )


def parse_ordering(params: Mapping[str, str]) -> Ordering:
    """Сортировка — списком уровней, с обратной совместимостью.

    `?ordering=-rating` остаётся рабочим и означает список из одного уровня;
    `?sort=-rating,reviews_count` задаёт несколько. Оба формата приняты
    одновременно, потому что фронтенд переключается на новый только в T153, а
    до тех пор обе реализации обязаны отвечать одинаково.
    """
    multi = params.get("sort")
    single = params.get("ordering")
    if multi and single:
        raise InvalidFilter("Use `sort` or `ordering`, not both")

    raw = multi or single
    if not raw:
        return Ordering()

    keys = tuple(_sort_key(chunk.strip()) for chunk in raw.split(",") if chunk.strip())
    if not keys:
        raise InvalidFilter("Sort must name at least one field")
    if len(keys) > MAX_SORT_KEYS:
        raise InvalidFilter(f"Sort accepts at most {MAX_SORT_KEYS} levels")

    fields = [key.field for key in keys]
    duplicated = sorted({field for field in fields if fields.count(field) > 1})
    if duplicated:
        raise InvalidFilter(f"Sort field repeated: {', '.join(duplicated)}")

    return Ordering(keys=keys)


def _sort_key(chunk: str) -> SortKey:
    descending = chunk.startswith("-")
    field = chunk[1:] if descending else chunk
    if field not in ORDERABLE_FIELDS:
        raise InvalidFilter(f"Cannot order by {field!r}; allowed: {sorted(ORDERABLE_FIELDS)}")
    return SortKey(field, descending=descending)


def parse_pagination(params: Mapping[str, str]) -> tuple[int, int]:
    """`(page, page_size)`.

    `page_size` выше предела **обрезается**, а не отвергается: так делает
    Django, и отказ вместо обрезания сломал бы клиента, который просит больше.
    """
    return (
        _positive(params, "page", default=1),
        min(_positive(params, "page_size", default=MAX_PAGE_SIZE), MAX_PAGE_SIZE),
    )


def _positive(params: Mapping[str, str], key: str, *, default: int) -> int:
    raw = params.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidFilter(f"{key} must be an integer") from exc
    if value < 1:
        raise InvalidFilter(f"{key} must be >= 1")
    return value

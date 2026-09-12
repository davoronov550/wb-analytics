"""Репозиторий товаров на SQLAlchemy (T124).

Два режима чтения, и это не переходное состояние.

`list` — страничный, реализует `ProductRepositoryPort` и повторяет поведение
Django дословно, включая порядок и смысл фильтров. Он нужен, пока внешний
контракт остаётся страничным: DoD T130 требует ответа, побайтово совпадающего
с Django.

`list_after` — keyset. Курсор приезжает в интерфейс на T152, но механизм
делается здесь, потому что от него зависит и индексирование (T125), и
нагрузочный тест (T142). Смещение на глубокой странице заставляет PostgreSQL
прочитать и выбросить всё, что до неё: `OFFSET 100000` стоит примерно столько
же, сколько чтение ста тысяч строк, и растёт линейно с номером страницы.

Цепочку условий keyset строит платформа (`libs/platform/pagination.py`), здесь
только перевод её абстрактных `Comparison` в SQLAlchemy. Разделение не
формальное: цепочка со смешанными направлениями — самая ошибкоопасная часть,
и она написана и проверена один раз на девять сервисов.
"""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.outbound.persistence.mappers import to_domain, to_row_values
from catalog.adapters.outbound.persistence.models import ProductRow, SearchQueryRow
from catalog.application.dto import Ordering, Page, ProductFilter, UpsertResult
from catalog.domain.product import Product
from wb_platform.pagination import (
    Comparison,
    Predicate,
    SortKey,
    SortSpec,
    build_page,
    keyset_predicate,
)
from wb_platform.pagination import Page as KeysetPage

__all__ = ["PRODUCT_TIEBREAKER", "SqlAlchemyProductRepository", "to_sort_spec"]

#: Чем разрываются ничьи. `wb_id`, а не суррогатный `id`: так делает Django
#: (`order_by(..., "wb_id")`), и совпадение порядка — часть паритета, который
#: проверяет T130. Колонка уникальна, поэтому годится в tiebreaker.
PRODUCT_TIEBREAKER = SortKey("wb_id", descending=False)

#: Поля сортировки в колонки. Явная таблица, а не `getattr(ProductRow, field)`:
#: имя поля приходит из HTTP, и обращение по нему к атрибутам модели открывает
#: доступ к чему угодно, включая `metadata` и `__table__`.
_SORTABLE: dict[str, sa.ColumnElement[Any]] = {
    "price": ProductRow.__table__.c.price,
    "sale_price": ProductRow.__table__.c.sale_price,
    "rating": ProductRow.__table__.c.rating,
    "reviews_count": ProductRow.__table__.c.reviews_count,
    "name": ProductRow.__table__.c.name,
    PRODUCT_TIEBREAKER.field: ProductRow.__table__.c.wb_id,
}


def to_sort_spec(ordering: Ordering) -> SortSpec:
    """`Ordering` прикладного слоя в `SortSpec` платформы.

    Перевод живёт в адаптере, а не в слое: `SortSpec` бросает собственную
    `ValidationError` платформы, и импорт его в `application/` подменил бы
    модель ошибок слоя.
    """
    return SortSpec(
        keys=tuple(SortKey(key.field, key.descending) for key in ordering.keys),
        tiebreaker=PRODUCT_TIEBREAKER,
    )


class SqlAlchemyProductRepository:
    """Реализация `ProductRepositoryPort` поверх asyncpg."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ чтение

    async def list(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        page: int,
        page_size: int,
    ) -> Page[Product]:
        """Страница по смещению — то же, что отдаёт Django.

        `COUNT(*)` отдельным запросом: интерфейс показывает общее число, и
        отказаться от него нельзя, пока контракт не сменился на курсорный.
        """
        base = self._filtered(filter)
        total = await self._session.scalar(sa.select(sa.func.count()).select_from(base.subquery()))
        page_query = (
            base.order_by(*self._order_by(ordering)).offset((page - 1) * page_size).limit(page_size)
        )
        return Page(
            items=await self._rows(page_query),
            count=total or 0,
            page=page,
            page_size=page_size,
        )

    async def list_after(
        self,
        filter: ProductFilter,
        ordering: Ordering,
        cursor_values: dict[str, Any] | None,
        limit: int,
    ) -> KeysetPage[Product]:
        """Страница после курсора — без смещения.

        Запрашивается `limit + 1` строка: лишняя отвечает на вопрос «есть ли
        следующая» дешевле, чем второй `COUNT(*)` по отфильтрованному набору.
        """
        spec = to_sort_spec(ordering)
        query = self._filtered(filter).order_by(*self._order_by(ordering))
        if cursor_values:
            query = query.where(self._as_sql(keyset_predicate(spec, cursor_values)))

        rows = (await self._session.execute(query.limit(limit + 1))).all()

        # Курсор строится по строкам таблицы, а не по доменным сущностям.
        # У `Product` цена — это `Money`, а рейтинг — `Rating`, и положить их в
        # курсор нельзя: он кодирует примитивы, потому что его читает и пишет
        # клиент. У строки те же поля лежат как `Decimal` и `int`.
        #
        # Разделение не косметическое: собери курсор из сущности — и он сломается
        # на первом же value object, причём не при записи, а при попытке
        # продолжить обход.
        paged = build_page([row for row, _ in rows], spec=spec, limit=limit)
        return KeysetPage(
            items=tuple(to_domain(row, source) for row, source in rows[:limit]),
            next_cursor=paged.next_cursor,
        )

    # ------------------------------------------------------------------ запись

    # `Sequence`, а не `list`: метод `list` ниже перекрывает встроенное имя
    # внутри тела класса, и `list[Product]` в аннотации разрешается в него.
    # Имя метода менять нельзя — оно приходит из порта.
    async def upsert_many(self, products: Sequence[Product], source_query: str) -> UpsertResult:
        """Вся пачка одним `INSERT ... ON CONFLICT`.

        Сбор приносит сотни товаров сразу, поэтому один запрос, а не запрос на
        товар. Разделение на созданные и обновлённые — часть контракта порта:
        оно видно в `ParseJob` и в ответе о статусе задачи. `ON CONFLICT` его
        не сообщает, поэтому уже существующие идентификаторы читаются заранее
        одним запросом, а числа получаются арифметикой множеств.
        """
        if not products:
            return UpsertResult(created=0, updated=0)

        query_row = await self._search_query(source_query)
        incoming = {product.wb_id: product for product in products}
        existing = set(
            (
                await self._session.scalars(
                    sa.select(ProductRow.wb_id).where(ProductRow.wb_id.in_(incoming))
                )
            ).all()
        )

        now = sa.func.now()
        statement = insert(ProductRow).values(
            [
                {
                    "wb_id": wb_id,
                    "source_query_id": query_row.id,
                    "created_at": now,
                    "updated_at": now,
                    **to_row_values(product),
                }
                for wb_id, product in incoming.items()
            ]
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[ProductRow.wb_id],
                # `created_at` отсутствует намеренно: повторно увиденный товар
                # сохраняет исходное время создания.
                set_={
                    "name": statement.excluded.name,
                    "price": statement.excluded.price,
                    "sale_price": statement.excluded.sale_price,
                    "rating": statement.excluded.rating,
                    "reviews_count": statement.excluded.reviews_count,
                    "source_query_id": statement.excluded.source_query_id,
                    "updated_at": statement.excluded.updated_at,
                },
            )
        )

        collected = await self._session.scalar(
            sa.select(sa.func.count())
            .select_from(ProductRow)
            .where(ProductRow.source_query_id == query_row.id)
        )
        query_row.collected_count = collected or 0

        return UpsertResult(
            created=len(incoming.keys() - existing),
            updated=len(incoming.keys() & existing),
        )

    # ----------------------------------------------------------------- частное

    def _filtered(self, filter: ProductFilter) -> sa.Select[Any]:
        """Условия — те же, что в Django, включая неочевидные.

        Границы цены применяются к `sale_price`, а не к `price`: фильтруется
        то, что платит покупатель. `query` сравнивается без учёта регистра
        (`iexact` у Django) и по точному совпадению, а не по вхождению.
        """
        query = sa.select(ProductRow, SearchQueryRow.text_).outerjoin(
            SearchQueryRow, ProductRow.source_query_id == SearchQueryRow.id
        )
        # `builtins.list`: см. примечание у `upsert_many` — метод `list`
        # перекрывает встроенное имя в теле класса.
        conditions: builtins.list[sa.ColumnElement[bool]] = []
        if filter.min_price is not None:
            conditions.append(ProductRow.sale_price >= filter.min_price)
        if filter.max_price is not None:
            conditions.append(ProductRow.sale_price <= filter.max_price)
        if filter.min_rating is not None:
            conditions.append(ProductRow.rating >= filter.min_rating)
        if filter.max_rating is not None:
            conditions.append(ProductRow.rating <= filter.max_rating)
        if filter.min_reviews is not None:
            conditions.append(ProductRow.reviews_count >= filter.min_reviews)
        if filter.max_reviews is not None:
            conditions.append(ProductRow.reviews_count <= filter.max_reviews)
        if filter.query:
            conditions.append(sa.func.lower(SearchQueryRow.text_) == filter.query.lower())
        return query.where(*conditions)

    @staticmethod
    def _order_by(ordering: Ordering) -> builtins.list[sa.UnaryExpression[Any]]:
        """ORDER BY со всеми уровнями и tiebreaker последним."""
        return [
            _SORTABLE[key.field].desc() if key.descending else _SORTABLE[key.field].asc()
            for key in to_sort_spec(ordering).all_keys
        ]

    @staticmethod
    def _as_sql(predicate: Predicate) -> sa.ColumnElement[bool]:
        """Абстрактная цепочка платформы в выражение SQLAlchemy.

        Дизъюнкция конъюнкций: `OR` по кортежам, внутри каждого `AND`.
        """
        return sa.or_(
            *(sa.and_(*(_comparison(term) for term in conjunction)) for conjunction in predicate)
        )

    async def _rows(self, query: sa.Select[Any]) -> builtins.list[Product]:
        result = await self._session.execute(query)
        return [to_domain(row, source_query) for row, source_query in result.all()]

    async def _search_query(self, text: str) -> SearchQueryRow:
        existing = await self._session.scalar(
            sa.select(SearchQueryRow).where(SearchQueryRow.text_ == text)
        )
        if existing is not None:
            return existing
        row = SearchQueryRow(text_=text, collected_count=0, created_at=sa.func.now())
        self._session.add(row)
        await self._session.flush()
        return row


def _comparison(term: Comparison) -> sa.ColumnElement[bool]:
    """Одно сравнение цепочки в выражение SQLAlchemy.

    Операторы на колонке с параметром типа `Any` возвращают `Any`, поэтому
    результат приводится явно: без этого `mypy --strict` не увидел бы, что
    условие вообще булево, и пропустил бы подстановку не того выражения.
    """
    column = _SORTABLE[term.field]
    if term.op == "=":
        expression = column == term.value
    elif term.op == "<":
        expression = column < term.value
    else:
        expression = column > term.value
    return cast("sa.ColumnElement[bool]", expression)

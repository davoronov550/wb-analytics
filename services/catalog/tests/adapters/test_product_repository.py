"""Репозиторий товаров против настоящего PostgreSQL (T124).

Главная проверка — обход keyset: страница за страницей до конца, и каждая
строка обязана встретиться ровно один раз. Это не тавтология. Если цепочка
условий построена наивно — кортежным сравнением `(a, b) > (:a, :b)` — то при
смешанных направлениях сортировки она даёт неверный результат, и симптом
именно такой: часть строк выпадает, часть приходит дважды. Заметить это на
одной странице невозможно, поэтому проверяется весь обход.

Третий пресет интерфейса как раз смешанный: цена по возрастанию, затем рейтинг
по убыванию. Ради него keyset и написан цепочкой, а не кортежом.

Данные подбираются так, чтобы ничьи были обязательно: без совпадающих значений
tiebreaker не участвует, и тест проходит при сломанном разрыве ничьих.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from catalog.adapters.outbound.persistence.repository import SqlAlchemyProductRepository
from catalog.application.dto import Ordering, ProductFilter, SortKey
from catalog.domain.product import Product
from catalog.domain.value_objects import Money, Rating, ReviewsCount

SERVICE = Path(__file__).resolve().parent.parent.parent

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

#: Пресеты `SortBuilder.tsx`. Третий — со смешанными направлениями.
PRESETS = {
    "отзывы ↓": (SortKey("reviews_count", descending=True),),
    "рейтинг ↓, отзывы ↓": (
        SortKey("rating", descending=True),
        SortKey("reviews_count", descending=True),
    ),
    "цена ↑, рейтинг ↓": (
        SortKey("sale_price", descending=False),
        SortKey("rating", descending=True),
    ),
}


def _alembic(command: str, dsn: str) -> None:
    import os

    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, "head" if command == "upgrade" else "base"],
        cwd=SERVICE,
        env={**os.environ, "DB_DSN": dsn, "SERVICE_NAME": "catalog"},
        capture_output=True,
        text=True,
        # Явная кодировка: по умолчанию Windows читает вывод в cp1252, а
        # сообщение миграции русское. Без этого диагностика ниже падала бы на
        # декодировании раньше, чем успела показать, что именно сломалось.
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic {command} упал:\n{result.stdout}\n{result.stderr}")


def _product(wb_id: int, *, sale: str, rating: str, reviews: int, name: str = "Товар") -> Product:
    return Product.rehydrate(
        wb_id=wb_id,
        name=f"{name} {wb_id}",
        price=Money(Decimal(sale) + Decimal("100.00")),
        sale_price=Money(Decimal(sale)),
        rating=Rating(Decimal(rating)),
        reviews_count=ReviewsCount(reviews),
        source_query="наушники",
    )


#: 60 товаров, в которых значения намеренно повторяются: 5 уровней цены,
#: 4 рейтинга, 6 значений отзывов. При 60 строках это гарантирует ничьи на
#: каждом уровне любого пресета — иначе tiebreaker не проверяется.
POPULATION = [
    _product(
        1000 + n,
        sale=f"{1000 + (n % 5) * 500}.00",
        rating=f"{1 + n % 4}.0",
        reviews=(n % 6) * 10,
    )
    for n in range(60)
]


@pytest_asyncio.fixture
async def repository(postgres_dsn: str) -> AsyncIterator[SqlAlchemyProductRepository]:
    """Пустая база под миграцией и репозиторий поверх неё."""
    _alembic("upgrade", postgres_dsn)
    engine = create_async_engine(postgres_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield SqlAlchemyProductRepository(session)
    finally:
        await engine.dispose()
        _alembic("downgrade", postgres_dsn)


@pytest_asyncio.fixture
async def populated(
    repository: SqlAlchemyProductRepository,
) -> SqlAlchemyProductRepository:
    await repository.upsert_many(POPULATION, "наушники")
    return repository


async def _walk_keyset(
    repository: SqlAlchemyProductRepository, ordering: Ordering, limit: int
) -> list[int]:
    """Все страницы подряд до конца — список `wb_id` в порядке обхода."""
    from wb_platform.pagination import decode_cursor

    seen: list[int] = []
    cursor_values: dict[str, Any] | None = None
    spec = None
    for _ in range(1000):  # предохранитель от бесконечного цикла на сломанной цепочке
        page = await repository.list_after(ProductFilter(), ordering, cursor_values, limit)
        seen.extend(product.wb_id for product in page.items)
        if page.next_cursor is None:
            return seen
        if spec is None:
            from catalog.adapters.outbound.persistence.repository import to_sort_spec

            spec = to_sort_spec(ordering)
        cursor_values = decode_cursor(spec, page.next_cursor)
    pytest.fail("обход не завершился за 1000 страниц — цепочка условий не двигает курсор")


class TestKeysetWalk:
    """DoD задачи: каждая строка ровно один раз, для всех трёх пресетов."""

    @pytest.mark.parametrize("preset", list(PRESETS), ids=list(PRESETS))
    @pytest.mark.parametrize("limit", [1, 7, 60], ids=["по одной", "по семь", "одной страницей"])
    async def test_every_row_exactly_once(
        self, populated: SqlAlchemyProductRepository, preset: str, limit: int
    ) -> None:
        walked = await _walk_keyset(populated, Ordering(keys=PRESETS[preset]), limit)

        assert len(walked) == len(POPULATION), "строк выпало или пришло лишних"
        assert len(set(walked)) == len(walked), "строка встретилась дважды"
        assert set(walked) == {p.wb_id for p in POPULATION}

    @pytest.mark.parametrize("preset", list(PRESETS), ids=list(PRESETS))
    async def test_walk_order_matches_a_single_query(
        self, populated: SqlAlchemyProductRepository, preset: str
    ) -> None:
        """Порядок обхода по страницам обязан совпасть с порядком одного
        запроса без пагинации. Расхождение здесь означает, что курсор
        переставляет строки между страницами."""
        ordering = Ordering(keys=PRESETS[preset])

        by_pages = await _walk_keyset(populated, ordering, limit=7)
        at_once = await _walk_keyset(populated, ordering, limit=len(POPULATION))

        assert by_pages == at_once


class TestOffsetPaging:
    """Страничное чтение — то, чем пользуется порт, пока контракт страничный."""

    async def test_pages_cover_everything_without_repeats(
        self, populated: SqlAlchemyProductRepository
    ) -> None:
        ordering = Ordering(keys=PRESETS["рейтинг ↓, отзывы ↓"])
        seen: list[int] = []
        for number in range(1, 7):
            page = await populated.list(ProductFilter(), ordering, number, 10)
            seen.extend(product.wb_id for product in page.items)

        assert len(set(seen)) == len(POPULATION)

    async def test_count_is_the_filtered_total_not_the_page(
        self, populated: SqlAlchemyProductRepository
    ) -> None:
        page = await populated.list(ProductFilter(), Ordering(), 1, 10)

        assert len(page.items) == 10
        assert page.count == len(POPULATION)

    async def test_offset_and_keyset_agree(self, populated: SqlAlchemyProductRepository) -> None:
        """Два режима чтения обязаны давать один порядок: иначе переход на
        курсор в T152 молча переставит товары в интерфейсе."""
        ordering = Ordering(keys=PRESETS["цена ↑, рейтинг ↓"])

        offset_page = await populated.list(ProductFilter(), ordering, 1, 15)
        keyset_page = await populated.list_after(ProductFilter(), ordering, None, 15)

        assert [p.wb_id for p in offset_page.items] == [p.wb_id for p in keyset_page.items]


class TestFiltersMatchDjango:
    """Условия, которые легко перенести неверно."""

    async def test_price_bounds_apply_to_the_discounted_price(
        self, populated: SqlAlchemyProductRepository
    ) -> None:
        """Фильтруется `sale_price`, а не `price`: то, что платит покупатель.
        Перепутать их — значит показать не тот набор при том же запросе."""
        page = await populated.list(
            ProductFilter(min_price=Decimal("1500"), max_price=Decimal("1500")),
            Ordering(),
            1,
            100,
        )

        assert page.items
        assert {p.sale_price.amount for p in page.items} == {Decimal("1500.00")}

    async def test_query_matches_ignoring_case(
        self, populated: SqlAlchemyProductRepository
    ) -> None:
        """У Django здесь `iexact`: точное совпадение без учёта регистра."""
        page = await populated.list(ProductFilter(query="НАУШНИКИ"), Ordering(), 1, 100)

        assert page.count == len(POPULATION)

    async def test_query_does_not_match_a_substring(
        self, populated: SqlAlchemyProductRepository
    ) -> None:
        """`iexact`, а не `icontains`: подстрока совпадать не должна."""
        page = await populated.list(ProductFilter(query="наушник"), Ordering(), 1, 100)

        assert page.count == 0


class TestUpsert:
    async def test_repeat_creates_no_duplicates(
        self, populated: SqlAlchemyProductRepository
    ) -> None:
        result = await populated.upsert_many(POPULATION, "наушники")

        assert (result.created, result.updated) == (0, len(POPULATION))
        page = await populated.list(ProductFilter(), Ordering(), 1, 1)
        assert page.count == len(POPULATION)

    async def test_repeat_keeps_the_original_creation_time(
        self, populated: SqlAlchemyProductRepository, postgres_dsn: str
    ) -> None:
        """`created_at` не входит в набор обновляемых колонок: повторно
        увиденный товар не должен выглядеть только что созданным."""
        engine = create_async_engine(postgres_dsn)
        try:
            before = await _created_at(engine, POPULATION[0].wb_id)
            await populated.upsert_many(POPULATION, "наушники")
            after = await _created_at(engine, POPULATION[0].wb_id)
        finally:
            await engine.dispose()

        assert before == after

    async def test_an_empty_batch_touches_nothing(
        self, repository: SqlAlchemyProductRepository
    ) -> None:
        """Пустой сбор — не ошибка: Wildberries отдаёт пустую выдачу по
        редкому запросу, и создавать под неё строку запроса незачем."""
        result = await repository.upsert_many([], "пусто")

        assert (result.created, result.updated) == (0, 0)


async def _created_at(engine: Any, wb_id: int) -> Any:
    async with engine.connect() as connection:
        return await connection.scalar(
            sa.text("SELECT created_at FROM catalog_product WHERE wb_id = :wb_id"),
            {"wb_id": wb_id},
        )

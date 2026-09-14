"""Сортировки пресетов обслуживаются индексом, а не сортировкой выборки (T125).

Пять сортируемых полей в произвольном порядке и направлении дают сотни
комбинаций — проиндексировать все нельзя. Индексируются три пресета интерфейса
и одиночные сортировки; остальное обслуживается медленнее и логируется (T126).

Проверяется планом запроса, а не временем: время на пустой базе ничего не
говорит, а план говорит прямо — `Index Scan using …` против `Sort`. Разница
между ними на выборке в сотни тысяч строк это разница между чтением пятидесяти
строк и сортировкой всей таблицы ради тех же пятидесяти.

Направления в индексе важны буквально. Индекс со смешанными порядками читается
только так, как создан: прочесть его «наоборот» PostgreSQL может лишь целиком,
инвертировав все уровни сразу, а для `(sale_price ASC, rating DESC)` обратное
чтение даёт `(sale_price DESC, rating ASC)` — другой порядок. Поэтому каждый
пресет проверяется отдельно и своим индексом.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

SERVICE = Path(__file__).resolve().parent.parent.parent

# `loop_scope="module"`: посев на пять тысяч строк делается один раз, а
# соединения движка принадлежат тому циклу событий, в котором созданы —
# без этого каждый тест получает свой цикл и падает на чужом соединении.
pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]

#: Строк в пробной таблице. Планировщик выбирает индекс по стоимости, и на
#: сотне строк полный проход дешевле — проверено: на 500 строках план ещё
#: `Sort`, на 2000 уже `Index Scan`. Пять тысяч берутся с запасом, чтобы тест
#: не начал мигать от правки статистики.
ROWS = 5000

#: Локаль базы. Совпадает с той, что зашита в индекс по `name`.
COLLATION = "en_US.utf8"

#: (описание, ORDER BY, ожидаемый индекс)
PRESETS = [
    (
        "отзывы ↓",
        "reviews_count DESC, wb_id ASC",
        "catalog_product_reviews_wb_idx",
    ),
    (
        "рейтинг ↓, отзывы ↓",
        "rating DESC, reviews_count DESC, wb_id ASC",
        "catalog_product_rating_reviews_wb_idx",
    ),
    (
        "цена ↑, рейтинг ↓",
        "sale_price ASC, rating DESC, wb_id ASC",
        "catalog_product_saleprice_rating_wb_idx",
    ),
    (
        "цена ↑",
        "price ASC, wb_id ASC",
        "catalog_product_price_wb_idx",
    ),
    (
        "название ↑",
        f'name COLLATE "{COLLATION}" ASC, wb_id ASC',
        "catalog_product_name_wb_idx",
    ),
]

# Три отдельных команды: asyncpg не выполняет несколько операторов одним
# запросом — он готовит их как prepared statement, а тот принимает ровно один.
_SEED = (
    sa.text(
        "INSERT INTO catalog_search_query (text, collected_count, created_at)"
        " VALUES ('наушники', 0, now())"
    ),
    sa.text(
        """
        INSERT INTO catalog_product
            (wb_id, name, price, sale_price, rating, reviews_count,
             created_at, updated_at, source_query_id)
        SELECT g, 'Товар ' || g,
               (1000 + (g % 400) * 25 + 100)::numeric(10,2),
               (1000 + (g % 400) * 25)::numeric(10,2),
               ((g % 50) / 10.0)::numeric(2,1),
               g % 500, now(), now(),
               (SELECT id FROM catalog_search_query LIMIT 1)
        FROM generate_series(1, :rows) g
        """
    ),
    # Без ANALYZE планировщик не знает размера таблицы и выбирает план по
    # умолчаниям — тест проверял бы отсутствие статистики, а не индексы.
    sa.text("ANALYZE catalog_product"),
)


def _alembic(command: str, dsn: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, "head" if command == "upgrade" else "base"],
        cwd=SERVICE,
        env={**os.environ, "DB_DSN": dsn, "SERVICE_NAME": "catalog"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic {command} упал:\n{result.stdout}\n{result.stderr}")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def seeded(postgres_dsn: str) -> AsyncIterator[AsyncEngine]:
    """Таблица со статистикой, на которой планировщику есть что выбирать."""
    _alembic("upgrade", postgres_dsn)
    engine = create_async_engine(postgres_dsn)
    async with engine.begin() as connection:
        for statement in _SEED:
            await connection.execute(statement, {"rows": ROWS} if ":rows" in str(statement) else {})
    try:
        yield engine
    finally:
        await engine.dispose()
        _alembic("downgrade", postgres_dsn)


async def _plan(engine: AsyncEngine, order_by: str) -> str:
    async with engine.connect() as connection:
        rows = await connection.execute(
            sa.text(
                f"EXPLAIN (COSTS OFF) SELECT * FROM catalog_product ORDER BY {order_by} LIMIT 50"
            )
        )
        return "\n".join(row[0] for row in rows)


class TestPresetsUseTheirIndex:
    @pytest.mark.parametrize(
        ("order_by", "index"),
        [(order_by, index) for _, order_by, index in PRESETS],
        ids=[label for label, _, _ in PRESETS],
    )
    async def test_index_scan(self, seeded: AsyncEngine, order_by: str, index: str) -> None:
        plan = await _plan(seeded, order_by)

        assert "Index Scan" in plan, f"сортировка выборки вместо индекса:\n{plan}"
        assert index in plan, f"использован не тот индекс:\n{plan}"


class TestCollationMustMatch:
    """Оговорка плана про `name`, проверенная, а не пересказанная."""

    async def test_matching_collation_uses_the_index(self, seeded: AsyncEngine) -> None:
        plan = await _plan(seeded, f'name COLLATE "{COLLATION}" ASC, wb_id ASC')

        assert "catalog_product_name_wb_idx" in plan

    async def test_a_different_collation_makes_the_index_useless(self, seeded: AsyncEngine) -> None:
        """Индекс, созданный с одной collation, для `ORDER BY` с другой просто
        не применяется: запрос тихо деградирует в сортировку всей выборки.

        Порядок при этом тоже другой — `C` сравнивает байты: 'Zebra' встаёт
        перед 'apple'. То есть несовпадение стоит не только производительности,
        но и того, что видит пользователь.
        """
        plan = await _plan(seeded, 'name COLLATE "C" ASC, wb_id ASC')

        assert "catalog_product_name_wb_idx" not in plan
        assert "Sort" in plan


class TestUnindexedCombinationStillWorks:
    async def test_it_is_served_but_not_by_a_matching_index(self, seeded: AsyncEngine) -> None:
        """Комбинация вне списка обязана работать — медленнее, но работать.
        Отказ вместо медленного ответа сломал бы интерфейс, который позволяет
        собрать произвольную сортировку."""
        plan = await _plan(seeded, "reviews_count ASC, price DESC, wb_id ASC")

        assert "Sort" in plan
        assert not any(index in plan for _, _, index in PRESETS[:3])

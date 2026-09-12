"""Начальная миграция описывает схему, которую оставил Django (T121).

Смысл задачи не в том, чтобы создать таблицы, а в том, чтобы описать
**уже существующие**: при выводе сервиса в прод он принимает базу Django, и
начальная ревизия там не выполняется, а признаётся (`alembic stamp head`).
Расхождение между описанием и реальностью всплыло бы первой же автогенерацией,
которая предложила бы пересоздать индексы поверх живых данных.

Сверка с самим Django здесь невозможна — он в другом виртуальном окружении и на
другой версии Python. Она делалась вручную и записана в докстринге миграции:
схемы, поднятые `alembic upgrade head` и `manage.py migrate`, совпали побайгово,
а `alembic check` на копии базы с 500 товарами не нашёл по таблицам каталога ни
одной операции.

Здесь закрепляется то, что проверяемо автоматически: миграция накатывается,
откатывается начисто и создаёт ровно те объекты, на которые опирается
репозиторий, — включая артефакты Django, выбрасывать которые нельзя.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

SERVICE = Path(__file__).resolve().parent.parent.parent

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _alembic(command: str, dsn: str) -> None:
    """Запуск alembic отдельным процессом.

    Не через API: `env.py` читает DSN из настроек при импорте, а импортируется
    он один раз на процесс — внутри тестов пришлось бы подменять уже
    загруженный модуль, и тест проверял бы подмену, а не миграцию.
    """
    target = "head" if command == "upgrade" else "base"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, target],
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


@pytest_asyncio.fixture
async def migrated(postgres_dsn: str) -> AsyncIterator[AsyncEngine]:
    """База, поднятая миграцией.

    Движок асинхронный: в проекте один драйвер, asyncpg, и синхронный
    `create_engine` потянул бы psycopg2 — второй драйвер ради интроспекции в
    тестах. Схему читаем через `run_sync`, как это и задумано в SQLAlchemy.
    """
    _alembic("upgrade", postgres_dsn)
    engine = create_async_engine(postgres_dsn)
    try:
        yield engine
    finally:
        await engine.dispose()
        _alembic("downgrade", postgres_dsn)


async def _inspect[T](engine: AsyncEngine, read: Callable[[sa.Inspector], T]) -> T:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync: read(sa.inspect(sync)))


class TestSchema:
    async def test_every_table_the_service_owns_is_created(self, migrated: AsyncEngine) -> None:
        names = set(await _inspect(migrated, lambda i: i.get_table_names()))

        assert {"catalog_product", "catalog_search_query", "catalog_parse_job"} <= names

    async def test_the_outbox_comes_with_it(self, migrated: AsyncEngine) -> None:
        """Единственное, чего у Django не было: без неё сервис не сможет
        публиковать события в одной транзакции с записью."""
        assert "outbox" in await _inspect(migrated, lambda i: i.get_table_names())

    @pytest.mark.parametrize(
        "index",
        [
            "catalog_pro_price_2d2a4c_idx",
            "catalog_pro_sale_pr_d20a45_idx",
            "catalog_pro_rating_67a263_idx",
            "catalog_pro_reviews_90b1f9_idx",
        ],
        ids=["price", "sale_price", "rating", "reviews_count"],
    )
    async def test_sorting_indexes_keep_their_django_names(
        self, migrated: AsyncEngine, index: str
    ) -> None:
        """Имена с хешами уродливы, но менять их — значит пересоздавать индексы
        на живой таблице ради косметики."""
        found = await _inspect(migrated, lambda i: i.get_indexes("catalog_product"))
        names = {index["name"] for index in found}

        assert index in names

    async def test_the_like_index_survived(self, migrated: AsyncEngine) -> None:
        """`varchar_pattern_ops` создаёт Django для поиска по префиксу. Он нам
        не нужен, но начальная миграция описывает схему, а не улучшает её:
        молча удалить индекс — это изменение, замаскированное под описание."""
        found = await _inspect(migrated, lambda i: i.get_indexes("catalog_search_query"))
        names = {index["name"] for index in found}

        assert "catalog_search_query_text_86d92da4_like" in names

    async def test_wb_id_is_unique(self, migrated: AsyncEngine) -> None:
        """Ключ идемпотентного upsert до миграции T122."""
        constraints = await _inspect(
            migrated, lambda i: i.get_unique_constraints("catalog_product")
        )

        assert any(c["column_names"] == ["wb_id"] for c in constraints)

    async def test_reviews_count_cannot_go_negative(self, migrated: AsyncEngine) -> None:
        """CHECK от `PositiveIntegerField`: домен это тоже проверяет, но база —
        последняя линия, и она не зависит от того, через какой код пришли."""
        async with migrated.begin() as connection:
            with pytest.raises(sa.exc.IntegrityError):
                await connection.execute(
                    sa.text(
                        "INSERT INTO catalog_product"
                        " (wb_id, name, price, sale_price, rating, reviews_count,"
                        "  created_at, updated_at)"
                        " VALUES (1, 'x', 1, 1, 1, -1, now(), now())"
                    )
                )


class TestRollback:
    async def test_downgrade_leaves_nothing_behind(self, postgres_dsn: str) -> None:
        """Откат начальной миграции — то, чем пользуются, когда вывод сервиса
        пошёл не так. Оставленная таблица сделает повторный накат невозможным."""
        _alembic("upgrade", postgres_dsn)
        _alembic("downgrade", postgres_dsn)

        engine = create_async_engine(postgres_dsn)
        try:
            tables = await _inspect(engine, lambda i: i.get_table_names())
        finally:
            await engine.dispose()
        remaining = set(tables) - {"alembic_version"}

        assert remaining == set()

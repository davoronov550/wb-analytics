"""Сервис работает через PgBouncer в транзакционном режиме (T127).

Пулер не оптимизация, а условие масштабирования репликами: PostgreSQL — процесс
на соединение, и девять сервисов по несколько реплик исчерпают
`max_connections` раньше, чем упрутся в процессор.

Проверять это нужно именно здесь, а не в нагрузочном тесте (T142): транзакционный
режим несовместим с prepared statements, отказ возникает только при
мультиплексировании нескольких клиентов на один backend, и обнаружить его под
нагрузкой в проде дороже, чем в тесте.

Насколько это не теория — измерено на живом окружении. При снятых защитах
платформы шестьдесят параллельных запросов через пулер дали 31 ответ 500:
`DuplicatePreparedStatementError` и 570 записей `InvalidSQLStatementNameError`
вида `prepared statement "__asyncpg_stmt_12__" does not exist`. С защитами —
шестьдесят ответов 200.

Отдельно стоит отметить: первая попытка воспроизвести отказ его **не** дала,
потому что мутация была неполной — снял размеры кешей, но оставил уникальные
имена statement-ов, и они в одиночку предотвращали коллизию. Три настройки в
`db.py` закрывают разные половины одной проблемы, и проверять их надо вместе.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from wb_platform.config import DatabaseSettings
from wb_platform.db import build_connect_args, create_engine

# Только `integration` на модуль: часть проверок синхронная — они читают
# аргументы подключения и базы не касаются. Маркер asyncio висит на классе,
# которому он нужен.
pytestmark = pytest.mark.integration

#: Адрес пулера в dev-окружении. Смещён от 5432, как и остальные порты: до
#: вывода Django из контура оба окружения работают одновременно.
PGBOUNCER_DSN = os.environ.get(
    "TEST_PGBOUNCER_DSN",
    "postgresql+asyncpg://wb_app:wbapp@127.0.0.1:16432/wb_catalog",
)

#: Параллельных запросов. Отказ возникает при мультиплексировании клиентов на
#: один backend, и на одном клиенте не воспроизводится вовсе.
CONCURRENCY = 40


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine() -> AsyncIterator[AsyncEngine]:
    settings = DatabaseSettings(dsn=PGBOUNCER_DSN, pgbouncer=True)
    created = create_engine(settings)
    try:
        yield created
    finally:
        await created.dispose()


class TestPinnedSettings:
    """Гарантии проверяются на аргументах, а не на построенном движке: читать
    их обратно значило бы лезть в приватные атрибуты пула SQLAlchemy — тест,
    который сломается на его следующем рефакторинге и ничего не скажет о нас."""

    def test_both_statement_caches_are_off(self) -> None:
        """Их именно два: свой у asyncpg и свой у диалекта SQLAlchemy.
        Отключить только первый недостаточно."""
        args = build_connect_args(DatabaseSettings(dsn=PGBOUNCER_DSN, pgbouncer=True))

        assert args["statement_cache_size"] == 0
        assert args["prepared_statement_cache_size"] == 0

    def test_statement_names_are_unique_per_connection(self) -> None:
        """asyncpg нумерует statement-ы последовательно и внутри соединения.
        За пулером счётчики разных клиентов идут независимо при общем backend,
        и двое занимают одно имя."""
        args = build_connect_args(DatabaseSettings(dsn=PGBOUNCER_DSN, pgbouncer=True))

        assert callable(args["prepared_statement_name_func"])
        first, second = (
            args["prepared_statement_name_func"](),
            args["prepared_statement_name_func"](),
        )
        assert first != second

    def test_passing_them_by_hand_is_refused(self) -> None:
        """Сервис не должен иметь возможности вернуть опасную настройку по
        невнимательности."""
        with pytest.raises(ValueError, match="fixed by the platform"):
            build_connect_args(
                DatabaseSettings(dsn=PGBOUNCER_DSN, pgbouncer=True),
                extra={"statement_cache_size": 100},
            )


@pytest.mark.asyncio(loop_scope="module")
class TestConcurrentTrafficThroughThePooler:
    async def test_the_pooler_answers(self, engine: AsyncEngine) -> None:
        async with engine.connect() as connection:
            assert await connection.scalar(sa.text("SELECT 1")) == 1

    async def test_many_clients_share_backends_without_collisions(
        self, engine: AsyncEngine
    ) -> None:
        """Тот самый случай. Один и тот же запрос, много клиентов, один пул
        backend-ов — без снятых защит отсюда сыпались бы
        `DuplicatePreparedStatementError`."""

        async def query(number: int) -> object:
            async with engine.connect() as connection:
                return await connection.scalar(sa.text("SELECT :n * 2"), {"n": number})

        results = await asyncio.gather(*(query(n) for n in range(CONCURRENCY)))

        assert results == [n * 2 for n in range(CONCURRENCY)]

    async def test_repeated_identical_queries_do_not_accumulate_state(
        self, engine: AsyncEngine
    ) -> None:
        """Повторение одного запроса — то, на чём кеш statement-ов и
        срабатывает: со второго раза клиент рассчитывает найти подготовленный
        statement, которого на новом backend нет."""
        for _ in range(3):
            results = await asyncio.gather(
                *(
                    self._scalar(engine, "SELECT count(*) FROM pg_stat_activity")
                    for _ in range(CONCURRENCY // 4)
                )
            )
            assert all(isinstance(value, int) for value in results)

    @staticmethod
    async def _scalar(engine: AsyncEngine, sql: str) -> object:
        async with engine.connect() as connection:
            return await connection.scalar(sa.text(sql))

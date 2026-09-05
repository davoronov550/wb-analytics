"""Alembic environment for the catalog service.

One migration history per service, because each owns its own database. A
shared history would reintroduce exactly the coupling the split removes: a
migration in `catalog` would block a deploy of `analytics`.

The DSN comes from settings rather than `alembic.ini` so migrations and the
service cannot disagree about which database they mean.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from wb_platform.config import DatabaseSettings
from wb_platform.outbox import outbox_metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The outbox table ships with the platform: every service that owns a database
# needs it, and nine hand-written copies would drift.
target_metadata = outbox_metadata

config.set_main_option("sqlalchemy.url", str(DatabaseSettings().dsn))


def run_migrations_offline() -> None:
    """Emit SQL without a connection — for reviewing a migration before it runs."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Without this a changed column type is silently skipped by
        # autogenerate, and the divergence surfaces as a runtime error.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool: a migration run is a single short-lived process. Pooling
        # would only leave connections open past the last statement.
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

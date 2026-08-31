"""Async PostgreSQL access shared by every service (T014).

One database per service, never a shared schema — that separation is the point
of the split, and a single ``create_engine`` here is what keeps nine services
from each rediscovering the same three settings.

**The setting this module exists to pin.** asyncpg prepares statements by
default. PgBouncer in transaction mode hands every transaction a different
backend connection, so a prepared statement created on one is absent on the
next: ``prepared statement "__asyncpg_stmt_1__" does not exist``. It appears
under load and never in development, where each process keeps its own
connection — so it cannot be left to whoever writes the next service to
remember. ``statement_cache_size`` is fixed at 0 and the key is refused if a
caller passes it at all (risk R8).

There are *two* caches, which is the trap: asyncpg keeps one, and SQLAlchemy's
asyncpg dialect keeps a second (``prepared_statement_cache_size``). Disabling
only the first still breaks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, Final
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from wb_platform.config import DatabaseSettings
from wb_platform.errors import ServiceUnavailableError

__all__ = [
    "build_connect_args",
    "build_engine_kwargs",
    "create_engine",
    "create_session_factory",
    "ping",
    "session_scope",
]

# Keys a caller may not supply: they carry a correctness decision, not a
# preference. Passing one — even with the right value — is refused, because
# allowing 0 today is how someone allows 100 tomorrow.
_PINNED_CONNECT_ARGS: Final[frozenset[str]] = frozenset(
    {
        "statement_cache_size",
        "prepared_statement_cache_size",
        "prepared_statement_name_func",
    }
)

_PING = text("SELECT 1")


def _unique_statement_name() -> str:
    """Name prepared statements uniquely instead of by a per-connection counter.

    The third PgBouncer trap, and the least obvious. asyncpg numbers statements
    ``__asyncpg_stmt_1__``, ``__asyncpg_stmt_2__`` … per connection. Behind a
    transaction-mode pooler those counters restart independently while the
    backend is shared, so two clients claim the same name and one gets
    ``DuplicatePreparedStatementError``. A UUID cannot collide.
    """
    return f"__asyncpg_{uuid4()}__"


def build_connect_args(
    settings: DatabaseSettings,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Driver arguments the engine will hand to asyncpg.

    A separate function so the safety guarantees can be asserted directly.
    Reading them back off a built engine would mean reaching into SQLAlchemy's
    private pool attributes — a test that breaks on their next refactor while
    saying nothing about ours.
    """
    supplied = dict(extra or {})
    forbidden = _PINNED_CONNECT_ARGS & supplied.keys()
    if forbidden:
        raise ValueError(
            f"{', '.join(sorted(forbidden))} is fixed by the platform and cannot be passed: "
            "PgBouncer in transaction mode is incompatible with prepared statements."
        )

    return {
        **supplied,
        # asyncpg's own cache.
        **settings.connect_args,
        # SQLAlchemy's dialect-level cache — the second of the two. It is a
        # DBAPI argument, not an engine one: the dialect pops it out of
        # connect_args and never sees it if passed to create_async_engine.
        "prepared_statement_cache_size": 0,
        # Guards against name collisions across pooled backends.
        "prepared_statement_name_func": _unique_statement_name,
        # Fail fast instead of hanging the readiness probe while the database
        # is unreachable.
        "timeout": settings.connect_timeout_seconds,
    }


def build_engine_kwargs(
    settings: DatabaseSettings,
    connect_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Every argument :func:`create_engine` passes to SQLAlchemy.

    Separate for the same reason as :func:`build_connect_args`: the settings
    that matter for correctness can then be asserted directly, instead of read
    back off a built engine through private pool attributes that break on the
    library's next refactor.
    """
    return {
        "connect_args": build_connect_args(settings, connect_args),
        "pool_size": settings.pool_size,
        "max_overflow": settings.max_overflow,
        # The counterpart of Django's CONN_HEALTH_CHECKS: without it the pool
        # hands out connections the server has already closed.
        "pool_pre_ping": True,
        "echo": settings.echo_sql,
    }


def create_engine(
    settings: DatabaseSettings,
    *,
    connect_args: dict[str, Any] | None = None,
) -> AsyncEngine:
    """Build the engine every service must use.

    ``connect_args`` is for genuinely service-specific driver options
    (``server_settings``, for instance). The PgBouncer-critical keys are not
    among them and are rejected rather than silently overridden — a silent
    override would produce an engine that looks configured and fails in
    production only.
    """
    return create_async_engine(str(settings.dsn), **build_engine_kwargs(settings, connect_args))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory for the composition root.

    ``expire_on_commit=False`` on purpose: the default re-fetches every
    attribute after a commit, and in async code that lazy load raises
    ``MissingGreenlet`` rather than merely being slow.
    """
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    factory: Callable[[], AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Run a unit of work: commit on success, roll back on any exception.

    The exception is re-raised. Swallowing it would leave a half-applied
    transaction and no signal that anything went wrong.
    """
    async with factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()


def _describe(exc: BaseException) -> str:
    """Render an exception for the log, including its type.

    ``str(exc)`` alone is not enough: an unreachable host surfaces as
    ``TimeoutError`` — an ``OSError`` subclass whose message is the empty
    string. Storing that verbatim leaves the operator with a 503 and nothing
    else, which is the outcome this whole ``context`` field exists to prevent.
    """
    detail = str(exc)
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


async def ping(engine: AsyncEngine) -> None:
    """Probe the database for ``/readyz``.

    A driver failure becomes :class:`ServiceUnavailableError`, so the probe
    answers 503 and the original message — which carries the DSN, host and role
    — goes to the log rather than to a public endpoint.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(_PING)
    except (SQLAlchemyError, OSError) as exc:
        raise ServiceUnavailableError(
            "Database is unavailable.",
            context={"cause": _describe(exc)},
        ) from exc

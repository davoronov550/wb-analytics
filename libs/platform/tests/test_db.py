"""Tests for database access (T014).

The contract under test: an engine built by this module is safe behind
PgBouncer in transaction mode, and there is no way to build an unsafe one.

Why that deserves its own guard. asyncpg prepares statements by default;
PgBouncer in transaction mode hands each transaction a different backend
connection, so the prepared statement is missing when it is reused. The failure
is ``prepared statement "__asyncpg_stmt_1__" does not exist`` under load, and it
does not reproduce in development, where every process holds its own
connection. Risk R8 in [док. 6](../../docs/migration/06-risks.md).
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self, cast

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from wb_platform.config import DatabaseSettings
from wb_platform.db import (
    build_connect_args,
    build_engine_kwargs,
    create_engine,
    create_session_factory,
    ping,
    session_scope,
)
from wb_platform.errors import ServiceUnavailableError

_DSN = "postgresql+asyncpg://wb_app:wbapp@localhost:5432/wb_catalog"


def _settings(**overrides: Any) -> DatabaseSettings:
    return DatabaseSettings(dsn=_DSN, **overrides)


def _connect_args(**extra: Any) -> dict[str, Any]:
    return build_connect_args(_settings(), extra or None)


# --------------------------------------------------------------------------
# Engine construction
# --------------------------------------------------------------------------


class TestEngine:
    def test_statement_cache_is_disabled(self) -> None:
        """The single setting that makes PgBouncer usable — risk R8."""
        assert _connect_args()["statement_cache_size"] == 0

    def test_dialect_level_prepared_statement_cache_is_disabled_too(self) -> None:
        """Two caches, two settings.

        asyncpg keeps its own statement cache and SQLAlchemy's asyncpg dialect
        keeps a second one. Disabling only the first still breaks behind
        PgBouncer, which is why this is asserted separately rather than trusted.
        """
        assert _connect_args()["prepared_statement_cache_size"] == 0

    def test_prepared_statement_names_are_unique(self) -> None:
        """The third PgBouncer trap: asyncpg numbers statements per connection.

        Behind a transaction-mode pooler those counters restart independently
        while the backend is shared, so two clients claim the same name and one
        gets DuplicatePreparedStatementError.
        """
        name_func = _connect_args()["prepared_statement_name_func"]

        assert name_func() != name_func()

    @pytest.mark.parametrize(
        "key",
        ["statement_cache_size", "prepared_statement_cache_size", "prepared_statement_name_func"],
    )
    def test_every_pinned_key_is_refused(self, key: str) -> None:
        with pytest.raises(ValueError, match=key):
            build_connect_args(_settings(), {key: 1})

    def test_caller_cannot_re_enable_the_statement_cache(self) -> None:
        """A well-meaning override is exactly how this regresses."""
        with pytest.raises(ValueError, match="statement_cache_size"):
            create_engine(_settings(), connect_args={"statement_cache_size": 100})

    def test_caller_cannot_pass_the_pinned_key_even_with_a_safe_value(self) -> None:
        """Refuse the key outright: allowing 0 invites allowing 1 next."""
        with pytest.raises(ValueError, match="statement_cache_size"):
            create_engine(_settings(), connect_args={"statement_cache_size": 0})

    def test_additional_connect_args_are_passed_through(self) -> None:
        connect_args = _connect_args(server_settings={"jit": "off"})

        assert connect_args["server_settings"] == {"jit": "off"}
        assert connect_args["statement_cache_size"] == 0

    def test_pre_ping_is_enabled(self) -> None:
        """Without it the pool hands out connections the server already closed.

        The Django settings enable CONN_HEALTH_CHECKS for the same reason; this
        is the SQLAlchemy equivalent, not a new precaution.
        """
        assert build_engine_kwargs(_settings())["pool_pre_ping"] is True

    def test_pool_sizing_comes_from_settings(self) -> None:
        kwargs = build_engine_kwargs(_settings(pool_size=7, max_overflow=3))

        assert (kwargs["pool_size"], kwargs["max_overflow"]) == (7, 3)

    def test_connect_timeout_is_applied(self) -> None:
        """Fail fast when PostgreSQL is unreachable, rather than hanging readyz."""
        assert build_connect_args(_settings(connect_timeout_seconds=1.5))["timeout"] == 1.5

    def test_echo_follows_settings(self) -> None:
        assert create_engine(_settings(echo_sql=True)).echo is True

    def test_engine_actually_builds_with_these_arguments(self) -> None:
        """Smoke test with real SQLAlchemy — no mock would have caught this.

        prepared_statement_cache_size looks like an engine keyword and is not:
        the dialect takes it as a DBAPI argument. Passing it the wrong way
        raises TypeError at construction, which only a real build reveals.
        """
        engine = create_engine(_settings())

        assert engine.url.database == "wb_catalog"
        assert engine.dialect.driver == "asyncpg"


# --------------------------------------------------------------------------
# Session scope
# --------------------------------------------------------------------------


class _FakeSession:
    """Records the transaction calls made against it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __aenter__(self) -> Self:
        self.calls.append("enter")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.calls.append("close")

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")


class TestSessionScope:
    @pytest.mark.asyncio
    async def test_commits_on_success(self) -> None:
        session = _FakeSession()

        async with session_scope(lambda: cast(AsyncSession, session)):
            pass

        assert session.calls == ["enter", "commit", "close"]

    @pytest.mark.asyncio
    async def test_rolls_back_and_re_raises_on_failure(self) -> None:
        """Swallowing here would leave a half-applied transaction and no error."""
        session = _FakeSession()

        with pytest.raises(ZeroDivisionError):
            async with session_scope(lambda: cast(AsyncSession, session)):
                raise ZeroDivisionError

        assert session.calls == ["enter", "rollback", "close"]

    @pytest.mark.asyncio
    async def test_does_not_commit_after_a_rollback(self) -> None:
        session = _FakeSession()

        with pytest.raises(RuntimeError):
            async with session_scope(lambda: cast(AsyncSession, session)):
                raise RuntimeError

        assert "commit" not in session.calls


class TestSessionFactory:
    def test_sessions_do_not_expire_attributes_on_commit(self) -> None:
        """`expire_on_commit=True` re-fetches every attribute after commit.

        In async code that lazy load raises MissingGreenlet instead of quietly
        being slow, so the default is the wrong one here.
        """
        factory = create_session_factory(create_engine(_settings()))

        assert factory.kw["expire_on_commit"] is False


# --------------------------------------------------------------------------
# Health probe
# --------------------------------------------------------------------------


class _FakeConnection:
    def __init__(self, *, fail: bool, error: BaseException | None = None) -> None:
        self._fail = fail
        self._error = error or SQLAlchemyError("connection refused to db:5432 for user wb_app")

    async def __aenter__(self) -> Self:
        if self._fail:
            raise self._error
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def execute(self, _statement: Any) -> None:
        return None


class _FakeEngine:
    def __init__(self, *, fail: bool = False, error: BaseException | None = None) -> None:
        self._fail = fail
        self._error = error

    def connect(self) -> _FakeConnection:
        return _FakeConnection(fail=self._fail, error=self._error)


class TestPing:
    @pytest.mark.asyncio
    async def test_succeeds_when_the_database_answers(self) -> None:
        await ping(cast(AsyncEngine, _FakeEngine()))

    @pytest.mark.asyncio
    async def test_failure_becomes_a_service_error_not_a_driver_error(self) -> None:
        """`/readyz` must answer 503, not leak a driver traceback."""
        with pytest.raises(ServiceUnavailableError):
            await ping(cast(AsyncEngine, _FakeEngine(fail=True)))

    @pytest.mark.asyncio
    async def test_cause_is_recorded_for_the_log(self) -> None:
        """503 without a reason anywhere is a dead end for whoever is on call."""
        with pytest.raises(ServiceUnavailableError) as exc:
            await ping(cast(AsyncEngine, _FakeEngine(fail=True)))

        assert "connection refused" in exc.value.context["cause"]

    @pytest.mark.asyncio
    async def test_cause_survives_an_exception_with_an_empty_message(self) -> None:
        """An unreachable host raises TimeoutError, whose str() is "".

        Found against a real database: the context field held an empty string,
        so the operator got a 503 and no diagnostic at all. The type name is
        now recorded even when the message is missing.
        """
        with pytest.raises(ServiceUnavailableError) as exc:
            await ping(cast(AsyncEngine, _FakeEngine(fail=True, error=TimeoutError())))

        assert exc.value.context["cause"] == "TimeoutError"

    @pytest.mark.asyncio
    async def test_driver_message_does_not_reach_the_caller(self) -> None:
        """The DSN and host live in that message; the probe is public."""
        with pytest.raises(ServiceUnavailableError) as exc:
            await ping(cast(AsyncEngine, _FakeEngine(fail=True)))

        assert "wb_app" not in exc.value.message
        assert "db:5432" not in exc.value.message

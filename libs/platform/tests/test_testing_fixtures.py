"""Tests for the integration-test fixtures (T022).

The fixtures themselves are exercised by the integration suites that use them
(``test_outbox.py`` already runs against real PostgreSQL). What is tested here
is the switch between the two ways of getting infrastructure — because getting
that wrong means CI silently pointing at a developer's local stack, or a
developer waiting on container startup they did not need.
"""

from __future__ import annotations

import pytest

from wb_platform.testing import use_compose


class TestComposeSwitch:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
    def test_enabled_by_the_usual_truthy_spellings(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("WB_TEST_USE_COMPOSE", value)

        assert use_compose() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", ""])
    def test_disabled_otherwise(self, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
        monkeypatch.setenv("WB_TEST_USE_COMPOSE", value)

        assert use_compose() is False

    def test_containers_are_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CI has no compose stack, so the safe default must be containers.

        The reverse default would have CI quietly connect to nothing, or worse,
        to whatever happens to be listening on those ports.
        """
        monkeypatch.delenv("WB_TEST_USE_COMPOSE", raising=False)

        assert use_compose() is False


@pytest.mark.integration
class TestComposeFixtures:
    """Only meaningful against the running dev stack."""

    def test_postgres_dsn_uses_the_async_driver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WB_TEST_USE_COMPOSE", "1")
        from wb_platform.testing import _COMPOSE_POSTGRES

        dsn = _COMPOSE_POSTGRES.format(database="wb_catalog")

        assert dsn.startswith("postgresql+asyncpg://")

    def test_redis_fixture_targets_an_isolated_database(self) -> None:
        """Test keys must not land in db 0, where a developer is looking."""
        from wb_platform.testing import _COMPOSE_REDIS

        assert _COMPOSE_REDIS.format(db=15).endswith("/15")

    def test_ports_avoid_the_legacy_django_stack(self) -> None:
        """backend/docker-compose.yml still owns 5432 and 6379 until phase 5."""
        from wb_platform.testing import _COMPOSE_POSTGRES, _COMPOSE_REDIS

        assert ":15432" in _COMPOSE_POSTGRES
        assert ":16379" in _COMPOSE_REDIS

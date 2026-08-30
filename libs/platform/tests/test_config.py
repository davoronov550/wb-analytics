"""Tests for the configuration base (T010).

The contract under test: a service must fail at startup when its configuration
is incomplete or malformed, never halfway through serving traffic.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from wb_platform.config import (
    DatabaseSettings,
    Environment,
    KafkaSettings,
    LogLevel,
    ObservabilitySettings,
    RedisSettings,
    ServiceSettings,
)


class TestServiceSettings:
    def test_reads_values_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "catalog")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("LOG_LEVEL", "warning")

        settings = ServiceSettings()

        assert settings.service_name == "catalog"
        assert settings.environment is Environment.PRODUCTION
        assert settings.log_level is LogLevel.WARNING

    def test_missing_required_field_fails_immediately(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SERVICE_NAME", raising=False)

        with pytest.raises(ValidationError) as exc:
            ServiceSettings()

        assert "service_name" in str(exc.value)

    def test_applies_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "catalog")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)

        settings = ServiceSettings()

        assert settings.environment is Environment.LOCAL
        assert settings.log_level is LogLevel.INFO

    def test_rejects_unknown_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "catalog")
        monkeypatch.setenv("ENVIRONMENT", "preprod")

        with pytest.raises(ValidationError):
            ServiceSettings()

    def test_is_immutable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "catalog")
        settings = ServiceSettings()

        with pytest.raises(ValidationError):
            settings.service_name = "other"

    def test_is_production_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SERVICE_NAME", "catalog")
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert ServiceSettings().is_production is True

        monkeypatch.setenv("ENVIRONMENT", "local")
        assert ServiceSettings().is_production is False


class TestDatabaseSettings:
    def test_reads_prefixed_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DB_DSN", "postgresql+asyncpg://u:p@localhost:5432/wb_catalog")
        monkeypatch.setenv("DB_POOL_SIZE", "25")

        settings = DatabaseSettings()

        assert settings.pool_size == 25
        assert "wb_catalog" in str(settings.dsn)

    def test_rejects_non_async_driver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A sync driver silently blocks the event loop — refuse it at startup.

        This is the single most expensive mistake available in an all-async
        stack, and it produces no error of its own: throughput just collapses.
        """
        monkeypatch.setenv("DB_DSN", "postgresql://u:p@localhost:5432/wb_catalog")

        with pytest.raises(ValidationError) as exc:
            DatabaseSettings()

        assert "asyncpg" in str(exc.value)

    def test_statement_cache_is_pinned_to_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PgBouncer in transaction mode is incompatible with prepared statements.

        Guards risk R8: the failure only reproduces under load, never in dev.
        """
        monkeypatch.setenv("DB_DSN", "postgresql+asyncpg://u:p@localhost:5432/wb_catalog")

        assert DatabaseSettings().connect_args == {"statement_cache_size": 0}

    def test_missing_dsn_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DB_DSN", raising=False)

        with pytest.raises(ValidationError):
            DatabaseSettings()


class TestKafkaSettings:
    def test_splits_bootstrap_servers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "a:9092, b:9092 ,c:9092")

        assert KafkaSettings().bootstrap_servers == ("a:9092", "b:9092", "c:9092")

    def test_rejects_empty_bootstrap_servers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "  ,  ")

        with pytest.raises(ValidationError):
            KafkaSettings()

    def test_manual_commit_is_the_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """At-least-once delivery requires committing after processing."""
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

        assert KafkaSettings().enable_auto_commit is False


class TestRedisSettings:
    def test_reads_dsn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REDIS_DSN", "redis://:pw@localhost:6379/0")

        assert "6379" in str(RedisSettings().dsn)


class TestObservabilitySettings:
    def test_defaults_to_full_sampling_outside_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OTEL_TRACE_SAMPLE_RATIO", raising=False)

        assert ObservabilitySettings().trace_sample_ratio == 1.0

    def test_rejects_sample_ratio_out_of_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OTEL_TRACE_SAMPLE_RATIO", "1.5")

        with pytest.raises(ValidationError):
            ObservabilitySettings()

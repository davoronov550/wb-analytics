"""Configuration base shared by every service (T010).

Two rules this module exists to enforce:

1. **Fail at startup, not in traffic.** A service with incomplete configuration
   must refuse to boot. Pydantic validation on instantiation gives us that for
   free — settings are built in the composition root, before the first request.
2. **Encode the traps that cost us production incidents.** Two are pinned here
   rather than left to each service: an async database driver (a sync one
   silently blocks the event loop) and ``statement_cache_size=0`` (PgBouncer in
   transaction mode is incompatible with prepared statements — risk R8).

Each group reads its own ``ENV_PREFIX``, so a Kubernetes manifest stays
readable: ``DB_DSN``, ``KAFKA_BOOTSTRAP_SERVERS``, ``REDIS_DSN``.

Services compose only what they need — api-gateway never instantiates
``DatabaseSettings``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Final

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

__all__ = [
    "DatabaseSettings",
    "Environment",
    "KafkaSettings",
    "LogLevel",
    "ObservabilitySettings",
    "RedisSettings",
    "ServiceSettings",
]

# Only asyncpg is supported. psycopg2/psycopg in sync mode would block the loop.
_REQUIRED_DB_DRIVER: Final = "postgresql+asyncpg"

# Pinned, not configurable: PgBouncer in transaction mode cannot reuse prepared
# statements across pooled connections, and asyncpg creates them by default.
_PGBOUNCER_SAFE_CONNECT_ARGS: Final[dict[str, Any]] = {"statement_cache_size": 0}


class Environment(StrEnum):
    LOCAL = "local"
    CI = "ci"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# Spread into every group's model_config. Kept as a plain literal rather than
# read back from `_Settings.model_config`: that attribute is the *resolved*
# config and already carries an `env_prefix` key, which collides on override.
_BASE_CONFIG: Final[SettingsConfigDict] = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    # Kubernetes injects dozens of unrelated variables (PATH, KUBERNETES_*),
    # so unknown keys cannot be an error.
    extra="ignore",
    # Settings are read once in the composition root and never mutated.
    frozen=True,
)


class _Settings(BaseSettings):
    """Shared behaviour: frozen, .env-aware, tolerant of unrelated variables."""

    model_config = SettingsConfigDict(**_BASE_CONFIG)


class ServiceSettings(_Settings):
    """Identity and log level — every service has these."""

    service_name: str
    environment: Environment = Environment.LOCAL
    log_level: LogLevel = LogLevel.INFO

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


class DatabaseSettings(_Settings):
    """PostgreSQL access. One database per service — never a shared schema."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="DB_")

    dsn: PostgresDsn
    # True when the DSN points at PgBouncer rather than PostgreSQL directly.
    # Not inferred from the host: a pooler can sit behind any name, and guessing
    # wrong picks the wrong pooling strategy silently. See db.build_engine_kwargs.
    pgbouncer: bool = False
    # Ignored when `pgbouncer` is set — NullPool takes no sizing arguments.
    pool_size: int = Field(default=10, ge=1)
    max_overflow: int = Field(default=5, ge=0)
    # Fail fast when PostgreSQL is unreachable instead of hanging the readiness
    # probe; the current Django settings use the same 2 s bound.
    connect_timeout_seconds: float = Field(default=2.0, gt=0)
    echo_sql: bool = False

    @field_validator("dsn")
    @classmethod
    def _require_async_driver(cls, value: PostgresDsn) -> PostgresDsn:
        if not str(value).startswith(_REQUIRED_DB_DRIVER):
            raise ValueError(
                f"DB_DSN must use the {_REQUIRED_DB_DRIVER!r} driver; "
                f"a synchronous driver blocks the event loop without raising."
            )
        return value

    @property
    def connect_args(self) -> dict[str, Any]:
        """Driver arguments that every engine in the platform must use."""
        return dict(_PGBOUNCER_SAFE_CONNECT_ARGS)


class KafkaSettings(_Settings):
    """Event bus access. Kafka 4.x in KRaft mode — no ZooKeeper anywhere."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="KAFKA_")

    # NoDecode: without it pydantic-settings JSON-parses complex types before
    # any validator runs, so a plain `a:9092,b:9092` never reaches _split_csv.
    bootstrap_servers: Annotated[tuple[str, ...], NoDecode]
    schema_registry_url: str | None = None
    consumer_group: str | None = None
    # At-least-once delivery: the offset moves only after the handler succeeds,
    # so a crash mid-processing replays the event instead of losing it.
    enable_auto_commit: bool = False
    max_poll_records: int = Field(default=500, ge=1)

    @field_validator("bootstrap_servers", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept ``a:9092, b:9092`` — the shape env vars and Helm values take."""
        if not isinstance(value, str):
            return value
        hosts = tuple(host.strip() for host in value.split(",") if host.strip())
        if not hosts:
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS must list at least one host")
        return hosts


class RedisSettings(_Settings):
    """Cache, rate limits, idempotency keys and alert dedup windows."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="REDIS_")

    dsn: RedisDsn
    socket_timeout_seconds: float = Field(default=2.0, gt=0)


class ObservabilitySettings(_Settings):
    """OpenTelemetry export. Disabled by default so tests need no collector."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="OTEL_")

    exporter_otlp_endpoint: str | None = None
    trace_sample_ratio: Annotated[float, Field(ge=0.0, le=1.0)] = 1.0
    sentry_dsn: str | None = None

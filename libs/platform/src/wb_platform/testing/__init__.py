"""Integration-test fixtures shared by every service (T022).

Real PostgreSQL, ClickHouse, Kafka and Redis — started once per test session
and reused. A mock of a database tests the mock; the failures worth catching
(``FOR UPDATE SKIP LOCKED`` semantics, ``ReplacingMergeTree`` deduplication,
consumer rebalancing) have no stand-in that behaves like the real thing.

**Reuse over isolation, deliberately.** A container per test would be correct
and unusably slow. Instead one container per session, with each test cleaning
up after itself — which is also closer to production, where the database is
never empty.

Two ways to get the infrastructure:

* **The dev compose stack**, when ``WB_TEST_USE_COMPOSE=1``. Instant, and what
  a developer already has running.
* **testcontainers** otherwise — ephemeral and what CI uses, where no compose
  stack exists.

Import these fixtures from a service's ``conftest.py``::

    from wb_platform.testing import *  # noqa: F403
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import pytest_asyncio

__all__ = [
    "clickhouse_url",
    "kafka_bootstrap",
    "postgres_dsn",
    "redis_dsn",
    "use_compose",
]


def use_compose() -> bool:
    """Whether to reuse the running dev stack instead of starting containers."""
    return os.environ.get("WB_TEST_USE_COMPOSE", "").lower() in {"1", "true", "yes"}


# Ports the dev stack publishes. Offset from the defaults because the legacy
# Django compose file still owns 5432 and 6379 until phase 5.
_COMPOSE_POSTGRES = "postgresql+asyncpg://wb_app:wbapp@127.0.0.1:15432/{database}"
_COMPOSE_REDIS = "redis://:devredis@127.0.0.1:16379/{db}"
_COMPOSE_KAFKA = "127.0.0.1:29092"
_COMPOSE_CLICKHOUSE = "http://wb_app:wbapp@127.0.0.1:8123/wb_analytics_test"


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    """A PostgreSQL DSN backed by the dev stack or a throwaway container."""
    if use_compose():
        yield _COMPOSE_POSTGRES.format(database="wb_catalog")
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def redis_dsn() -> Iterator[str]:
    if use_compose():
        # Database 15: keeps test keys away from anything a developer is
        # looking at in db 0.
        yield _COMPOSE_REDIS.format(db=15)
        return

    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7") as container:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"


@pytest.fixture(scope="session")
def kafka_bootstrap() -> Iterator[str]:
    if use_compose():
        yield _COMPOSE_KAFKA
        return

    from testcontainers.kafka import KafkaContainer

    # KRaft mode: Kafka 4.0 removed ZooKeeper, so a ZooKeeper-based container
    # would not start at all.
    with KafkaContainer("apache/kafka:4.0.0").with_kraft() as container:
        yield container.get_bootstrap_server()


@pytest.fixture(scope="session")
def clickhouse_url() -> Iterator[str]:
    if use_compose():
        yield _COMPOSE_CLICKHOUSE
        return

    from testcontainers.clickhouse import ClickHouseContainer

    with ClickHouseContainer("clickhouse/clickhouse-server:24.8-alpine") as container:
        yield container.get_connection_url()


@pytest_asyncio.fixture
async def clean_redis(redis_dsn: str) -> AsyncIterator[Any]:
    """A Redis client whose keys are wiped after the test.

    Flushing after rather than before: a failed test leaves its keys behind for
    inspection, and the next run starts clean regardless.
    """
    from redis.asyncio import Redis

    client: Any = Redis.from_url(redis_dsn, decode_responses=True)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()

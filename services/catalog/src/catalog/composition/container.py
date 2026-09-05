"""Composition root — the single place dependencies are built.

Ports are resolved to adapters here and nowhere else. That is what keeps
`domain/` and `application/` free of frameworks, which in turn is what let
~1 800 lines move from Django to FastAPI by copying rather than rewriting.

Health checks are registered alongside the thing they check, so a dependency
cannot be added without ``/readyz`` learning about it.
"""

from __future__ import annotations

from typing import Any

from wb_platform.config import ServiceSettings
from wb_platform.health import HealthRegistry
from wb_platform.logging import get_logger

logger = get_logger(__name__)


class Container:
    """Owns every long-lived resource the service holds."""

    def __init__(self, settings: ServiceSettings) -> None:
        self._settings = settings
        self._engine: Any = None
        self._redis: Any = None
        self._kafka: Any = None

    async def start(self) -> None:
        """Open connections. Raising here stops the service from starting."""
        from wb_platform.config import DatabaseSettings
        from wb_platform.db import create_engine, create_session_factory

        self._engine = create_engine(DatabaseSettings())
        self.session_factory = create_session_factory(self._engine)
        from wb_platform.config import KafkaSettings

        self._kafka_settings = KafkaSettings()
        logger.info("Container started")

    async def stop(self) -> None:
        """Release everything, in reverse order of acquisition."""
        if self._engine is not None:
            await self._engine.dispose()
        logger.info("Container stopped")

    def register_health_checks(self, registry: HealthRegistry) -> None:
        """Attach a readiness check per dependency that gates serving traffic.

        The database is one: a request that needs it cannot be answered without
        it, so reporting ready would just move the failure later.

        Kafka deliberately is not. Publishing goes through the transactional
        outbox, so a broker that is down delays delivery instead of losing it,
        and the relay drains the backlog when it returns — refusing traffic
        meanwhile would turn a recoverable outage into an outage of this
        service too. Register a probe here only for a dependency whose absence
        makes a request unanswerable.
        """
        from wb_platform.db import ping

        async def database() -> None:
            await ping(self._engine)

        registry.register("database", database)

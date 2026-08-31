"""Kafka producer and consumer shared by every service (T018).

Two rules, both of which are easy to get backwards and expensive to discover
in production.

**Commit after processing, never before.** ``enable_auto_commit`` moves the
offset on a timer, so a handler that crashes mid-work has already had its
message marked consumed — the event is gone and nothing says so. Committing
after the handler returns converts that silent loss into a redelivery.

**Redelivery therefore has to be harmless.** At-least-once means every consumer
sees some messages twice: after a crash, a rebalance, or a relay republishing
what the outbox still held (T016). Deduplicating by ``event_id`` here means
each handler does not have to remember to.

The two rules are one design: you cannot have the safe commit order without
idempotent consumers, and idempotent consumers are wasted without it.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from wb_platform.logging import bind_context, clear_context, get_logger
from wb_platform.otel import (
    extract_from_kafka_headers,
    inject_into_kafka_headers,
    traced,
)

__all__ = [
    "DedupStore",
    "EventConsumer",
    "EventProducer",
    "InboundMessage",
    "RedisDedupStore",
]

_EVENT_ID_HEADER: Final = "event_id"
_ENCODING: Final = "utf-8"

#: How long a processed ``event_id`` is remembered. Long enough to cover a
#: rebalance or a relay retry; short enough that the set does not grow forever.
DEFAULT_DEDUP_TTL_SECONDS: Final = 24 * 60 * 60

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """A consumed record, already decoded enough to route and deduplicate."""

    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: bytes
    headers: tuple[tuple[str, bytes], ...] = field(default_factory=tuple)

    @property
    def event_id(self) -> str | None:
        for name, raw in self.headers:
            if name == _EVENT_ID_HEADER:
                return raw.decode(_ENCODING, errors="replace")
        return None


class DedupStore(Protocol):
    """Remembers which ``event_id`` values have already been handled."""

    async def seen(self, event_id: str) -> bool:
        """Record the id and report whether it was already present."""
        ...


class RedisDedupStore:
    """``SET NX`` is the whole mechanism: the first writer wins."""

    def __init__(
        self,
        redis: Any,
        *,
        namespace: str,
        ttl_seconds: int = DEFAULT_DEDUP_TTL_SECONDS,
    ) -> None:
        self._redis = redis
        self._namespace = namespace
        self._ttl = ttl_seconds

    async def seen(self, event_id: str) -> bool:
        claimed = await self._redis.set(
            f"dedup:{self._namespace}:{event_id}", "1", ex=self._ttl, nx=True
        )
        return not claimed


class _AioKafkaProducer(Protocol):
    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: Sequence[tuple[str, bytes]] | None = None,
    ) -> Any: ...


class EventProducer:
    """Publishes events with an id and the trace context attached."""

    def __init__(self, producer: _AioKafkaProducer) -> None:
        self._producer = producer

    async def publish(
        self,
        topic: str,
        *,
        key: str,
        payload: bytes,
        event_id: str | None = None,
        headers: Sequence[tuple[str, bytes]] | None = None,
    ) -> str:
        """Send one event; returns its ``event_id``.

        The id is a header rather than part of the payload so a consumer can
        deduplicate without deserialising — which matters when the schema it
        would need is one it cannot read.
        """
        identifier = event_id or str(uuid.uuid4())
        with traced(f"publish {topic}", attributes={"messaging.destination": topic}):
            enriched = inject_into_kafka_headers(
                [*(headers or []), (_EVENT_ID_HEADER, identifier.encode(_ENCODING))]
            )
            await self._producer.send_and_wait(
                topic, payload, key=key.encode(_ENCODING), headers=enriched
            )
        return identifier


#: A handler signals success by returning and failure by raising.
Handler = Callable[[InboundMessage], Awaitable[None]]


class EventConsumer:
    """Runs a handler per message with dedup, tracing and a safe commit order."""

    def __init__(
        self,
        *,
        dedup: DedupStore | None = None,
        require_event_id: bool = True,
    ) -> None:
        self._dedup = dedup
        self._require_event_id = require_event_id

    async def handle(self, message: InboundMessage, handler: Handler) -> bool:
        """Process one message. Returns whether the offset may be committed.

        A handler that raises returns ``False`` — the offset stays put and the
        message is redelivered. That is the point: a lost event is invisible,
        while a redelivered one is absorbed by the dedup above.
        """
        parent = extract_from_kafka_headers(message.headers)

        with traced(
            f"consume {message.topic}",
            parent=parent,
            attributes={
                "messaging.source": message.topic,
                "messaging.kafka.partition": message.partition,
                "messaging.kafka.offset": message.offset,
            },
        ):
            event_id = message.event_id
            if event_id is None:
                if self._require_event_id:
                    # Not retryable: redelivering will not grow the header.
                    # Commit past it and record what was skipped.
                    logger.error(
                        "Message without event_id skipped",
                        topic=message.topic,
                        partition=message.partition,
                        offset=message.offset,
                    )
                    return True
            elif self._dedup is not None and await self._dedup.seen(event_id):
                logger.info("Duplicate event skipped", topic=message.topic, event_id=event_id)
                return True

            bind_context(event_id=event_id)
            try:
                await handler(message)
            except Exception:
                # Deliberately no commit. Logged here because the caller only
                # learns that the offset did not move.
                logger.exception(
                    "Handler failed; offset not committed",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
                return False
            finally:
                clear_context()

        return True

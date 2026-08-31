"""Kafka producer and consumer shared by every service (T018).

Delivery is at-least-once end to end, and every piece below exists because one
specific failure would otherwise lose a message silently.

**Where messages actually go missing**

* *Producer → broker.* ``acks=1`` returns success as soon as the partition
  leader has the record. If that leader dies before followers replicate, the
  record is gone and the producer was told it succeeded. ``acks="all"`` with
  ``min.insync.replicas=2`` is what makes the acknowledgement mean something.
* *Producer retries.* A retry after a timeout can append the record twice —
  the first attempt succeeded, the acknowledgement was lost.
  ``enable_idempotence=True`` makes the broker discard the duplicate.
* *Consumer offsets.* ``enable_auto_commit=True`` moves the offset on a timer,
  so a handler that crashes mid-work has already had its message marked
  consumed. Committing after the handler converts silent loss into redelivery.
* *A new consumer group.* aiokafka defaults ``auto_offset_reset`` to
  ``"latest"``: a group reading a topic for the first time skips everything
  already in it. For an analytics backfill that is total, silent data loss.

**Deduplication is an optimisation, not a guarantee**

The ``event_id`` is recorded **after** the handler succeeds. Recording it
before — which this module did in its first version — means a redelivery
following a handler failure is skipped as a duplicate, so the message is
delivered and never processed. That is the very loss the commit order exists
to prevent.

Marking afterwards leaves a smaller window: a crash between the handler
finishing and the mark being written causes the handler to run twice. So
handlers still have to be idempotent where it counts — ``ON CONFLICT DO
NOTHING`` in PostgreSQL, ``ReplacingMergeTree`` in ClickHouse. The dedup saves
redundant work; the data layer is what saves correctness.

**Poison messages**

A message that fails every time would otherwise be retried forever, and since
Kafka delivers a partition in order, everything behind it stops too — one bad
record halts a partition indefinitely. After ``max_attempts`` the message goes
to ``<topic>.dlq`` and the offset advances.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final, Protocol

from wb_platform.logging import bind_context, clear_context, get_logger
from wb_platform.otel import (
    extract_from_kafka_headers,
    inject_into_kafka_headers,
    traced,
)

__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DedupStore",
    "EventConsumer",
    "EventProducer",
    "InboundMessage",
    "Outcome",
    "RedisDedupStore",
    "consumer_config",
    "dlq_topic",
    "producer_config",
]

_EVENT_ID_HEADER: Final = "event_id"
_ENCODING: Final = "utf-8"

#: How long a processed ``event_id`` is remembered. Long enough to cover a
#: rebalance or a relay republishing from the outbox.
DEFAULT_DEDUP_TTL_SECONDS: Final = 24 * 60 * 60

#: Attempts before a message is treated as poison. Kafka delivers a partition
#: in order, so retrying forever stops every message behind it too.
DEFAULT_MAX_ATTEMPTS: Final = 5

logger = get_logger(__name__)


def producer_config(**overrides: Any) -> dict[str, Any]:
    """Producer settings with the durability guarantees turned on.

    A factory rather than documentation, because aiokafka's defaults are the
    unsafe ones and nine services would each have to remember to change them.
    """
    config: dict[str, Any] = {
        # Every in-sync replica must have the record before it is acknowledged.
        # With acks=1 a leader failure loses records the producer was told
        # were written.
        "acks": "all",
        # Deduplicates producer retries at the broker: without it, a retry
        # after a lost acknowledgement appends the record a second time.
        "enable_idempotence": True,
    }
    config.update(overrides)
    return config


def consumer_config(*, group_id: str, **overrides: Any) -> dict[str, Any]:
    """Consumer settings with the offset handled explicitly."""
    config: dict[str, Any] = {
        "group_id": group_id,
        # Offsets move only after a handler returns.
        "enable_auto_commit": False,
        # aiokafka defaults to "latest", which makes a new consumer group skip
        # everything already in the topic — silent and total for a backfill.
        "auto_offset_reset": "earliest",
    }
    config.update(overrides)
    return config


def dlq_topic(topic: str) -> str:
    """Where messages go once they are established as poison."""
    return f"{topic}.dlq"


class Outcome(StrEnum):
    """What the poll loop should do with the offset."""

    COMMIT = "commit"
    """Handled, or deliberately skipped. Advance."""

    RETRY = "retry"
    """Failed but worth another attempt. Leave the offset where it is."""

    DEAD_LETTER = "dead_letter"
    """Out of attempts. Routed to the DLQ; advance so the partition moves on."""


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """A consumed record, decoded enough to route and deduplicate."""

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
    """Tracks which events are done and how often each has been attempted."""

    async def is_processed(self, event_id: str) -> bool: ...

    async def mark_processed(self, event_id: str) -> None: ...

    async def record_attempt(self, event_id: str) -> int:
        """Increment and return the attempt count for this event."""
        ...

    async def forget_attempts(self, event_id: str) -> None: ...


class RedisDedupStore:
    """Redis-backed dedup and attempt counter."""

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

    def _done_key(self, event_id: str) -> str:
        return f"dedup:{self._namespace}:{event_id}"

    def _attempt_key(self, event_id: str) -> str:
        return f"attempts:{self._namespace}:{event_id}"

    async def is_processed(self, event_id: str) -> bool:
        return bool(await self._redis.exists(self._done_key(event_id)))

    async def mark_processed(self, event_id: str) -> None:
        await self._redis.set(self._done_key(event_id), "1", ex=self._ttl)

    async def record_attempt(self, event_id: str) -> int:
        key = self._attempt_key(event_id)
        count = int(await self._redis.incr(key))
        if count == 1:
            # Expire alongside the dedup record; a counter that outlived it
            # would send a legitimately redelivered event straight to the DLQ.
            await self._redis.expire(key, self._ttl)
        return count

    async def forget_attempts(self, event_id: str) -> None:
        await self._redis.delete(self._attempt_key(event_id))


#: A handler signals success by returning and failure by raising.
Handler = Callable[[InboundMessage], Awaitable[None]]

#: Publishes a message that has exhausted its attempts.
DeadLetterSink = Callable[[InboundMessage, str], Awaitable[None]]


class EventConsumer:
    """Runs a handler per message with dedup, retries, tracing and a DLQ."""

    def __init__(
        self,
        *,
        dedup: DedupStore | None = None,
        dead_letter: DeadLetterSink | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        require_event_id: bool = True,
    ) -> None:
        self._dedup = dedup
        self._dead_letter = dead_letter
        self._max_attempts = max_attempts
        self._require_event_id = require_event_id

    async def handle(self, message: InboundMessage, handler: Handler) -> Outcome:
        """Process one message and say what to do with the offset."""
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

            if event_id is None and self._require_event_id:
                # Not retryable: redelivery will not grow the header.
                logger.error(
                    "Message without event_id sent to the dead-letter topic",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
                return await self._to_dead_letter(message, "missing event_id")

            if (
                event_id is not None
                and self._dedup is not None
                and await self._dedup.is_processed(event_id)
            ):
                logger.info("Duplicate event skipped", topic=message.topic, event_id=event_id)
                return Outcome.COMMIT

            return await self._run(message, handler, event_id)

    async def _run(
        self, message: InboundMessage, handler: Handler, event_id: str | None
    ) -> Outcome:
        bind_context(event_id=event_id)
        try:
            await handler(message)
        except Exception as exc:
            return await self._on_failure(message, event_id, exc)
        else:
            # Only now. Marking before the handler would turn a redelivery
            # after a failure into a skipped duplicate — the message would be
            # delivered and never processed.
            if event_id is not None and self._dedup is not None:
                await self._dedup.mark_processed(event_id)
                await self._dedup.forget_attempts(event_id)
            return Outcome.COMMIT
        finally:
            clear_context()

    async def _on_failure(
        self, message: InboundMessage, event_id: str | None, exc: Exception
    ) -> Outcome:
        attempts = 1
        if event_id is not None and self._dedup is not None:
            attempts = await self._dedup.record_attempt(event_id)

        if attempts >= self._max_attempts:
            # Kafka delivers a partition in order, so retrying this one forever
            # stops every message behind it as well.
            logger.error(
                "Message exhausted its attempts; routing to the dead-letter topic",
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                attempts=attempts,
                error=type(exc).__name__,
            )
            return await self._to_dead_letter(message, f"{type(exc).__name__}: {exc}")

        logger.warning(
            "Handler failed; offset not committed",
            topic=message.topic,
            partition=message.partition,
            offset=message.offset,
            attempt=attempts,
            error=type(exc).__name__,
        )
        return Outcome.RETRY

    async def _to_dead_letter(self, message: InboundMessage, reason: str) -> Outcome:
        if self._dead_letter is None:
            # Without a sink the only choices are dropping the message or
            # halting the partition. Halting is louder, and a stuck partition
            # is visible in consumer lag within seconds.
            logger.error(
                "No dead-letter sink configured; partition will stall",
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                reason=reason,
            )
            return Outcome.RETRY

        await self._dead_letter(message, reason)
        return Outcome.DEAD_LETTER


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

        The id travels as a header rather than inside the payload so a consumer
        can deduplicate without deserialising — which matters when the schema it
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

    async def dead_letter(self, message: InboundMessage, reason: str) -> None:
        """Publish a failed message to ``<topic>.dlq`` with why it got there.

        The original headers are kept — including ``traceparent``, so the DLQ
        entry is still joined to the trace that produced it — and the reason is
        added alongside.
        """
        with traced(f"dead-letter {message.topic}"):
            headers = [
                *message.headers,
                ("dlq_reason", reason.encode(_ENCODING)),
                ("dlq_source_topic", message.topic.encode(_ENCODING)),
                (
                    "dlq_source_offset",
                    json.dumps({"partition": message.partition, "offset": message.offset}).encode(
                        _ENCODING
                    ),
                ),
            ]
            await self._producer.send_and_wait(
                dlq_topic(message.topic), message.value, key=message.key, headers=headers
            )

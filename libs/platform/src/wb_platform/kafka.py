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

from wb_platform.errors import ServiceUnavailableError
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
    "TopicProblem",
    "TopicSpec",
    "consumer_config",
    "dlq_topic",
    "ensure_topics",
    "producer_config",
    "require_durable_topics",
    "verify_topics",
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


# --------------------------------------------------------------------------
# Topic durability
# --------------------------------------------------------------------------

#: Replicas a topic needs to survive losing a broker.
DURABLE_REPLICATION_FACTOR: Final = 3

#: Replicas that must acknowledge before a write is confirmed.
#:
#: This is the number that gives ``acks="all"`` its meaning. At 1 — aiokafka's
#: and Kafka's default — "all in-sync replicas" is satisfied by the leader
#: alone, so ``acks="all"`` behaves exactly like ``acks=1`` and a leader
#: failure loses acknowledged writes. Setting one without the other is not a
#: partial guarantee; it is no guarantee.
DURABLE_MIN_INSYNC_REPLICAS: Final = 2


@dataclass(frozen=True, slots=True)
class TopicSpec:
    """How a topic must be configured for its writes to be durable."""

    name: str
    partitions: int = 3
    replication_factor: int = DURABLE_REPLICATION_FACTOR
    min_insync_replicas: int = DURABLE_MIN_INSYNC_REPLICAS
    retention_ms: int | None = None

    def topic_configs(self) -> dict[str, str]:
        configs = {
            "min.insync.replicas": str(self.min_insync_replicas),
            # Never promote a replica that is behind: doing so trades a
            # short outage for permanent data loss.
            "unclean.leader.election.enable": "false",
        }
        if self.retention_ms is not None:
            configs["retention.ms"] = str(self.retention_ms)
        return configs


@dataclass(frozen=True, slots=True)
class TopicProblem:
    topic: str
    setting: str
    expected: str
    actual: str

    def __str__(self) -> str:
        return f"{self.topic}: {self.setting} is {self.actual}, expected {self.expected}"


class _AdminClient(Protocol):
    async def describe_topics(self, topics: list[str]) -> list[dict[str, Any]]: ...

    async def describe_configs(self, resources: list[Any]) -> list[Any]: ...

    async def create_topics(self, new_topics: list[Any]) -> Any: ...


def _config_entries(response: Any) -> dict[str, str]:
    """Pull ``{name: value}`` out of a DescribeConfigs response.

    The protocol object is nested tuples rather than a documented structure,
    so this is deliberately defensive: a shape change should surface as an
    empty mapping and a failed check, not an IndexError at startup.
    """
    try:
        resource = response.resources[0]
        return {entry[0]: entry[1] for entry in resource[4]}
    except (AttributeError, IndexError, TypeError):
        return {}


async def verify_topics(admin: _AdminClient, specs: Sequence[TopicSpec]) -> list[TopicProblem]:
    """Report every topic whose durability settings fall short.

    Reads the broker rather than trusting the deployment: a topic created by
    hand, by an older chart, or auto-created by a producer has none of these
    settings, and nothing about the running system says so.
    """
    from aiokafka.admin.config_resource import ConfigResource, ConfigResourceType

    problems: list[TopicProblem] = []

    described = await admin.describe_topics([spec.name for spec in specs])
    by_name = {item["topic"]: item for item in described}

    configs = await admin.describe_configs(
        [ConfigResource(ConfigResourceType.TOPIC, spec.name) for spec in specs]
    )
    entries_by_name = {
        spec.name: _config_entries(response) for spec, response in zip(specs, configs, strict=False)
    }

    for spec in specs:
        described_topic = by_name.get(spec.name)
        if described_topic is None or described_topic.get("error_code"):
            problems.append(TopicProblem(spec.name, "existence", "present", "missing"))
            continue

        partitions = described_topic.get("partitions") or []
        actual_rf = min((len(p.get("replicas") or []) for p in partitions), default=0)
        if actual_rf < spec.replication_factor:
            problems.append(
                TopicProblem(
                    spec.name, "replication.factor", str(spec.replication_factor), str(actual_rf)
                )
            )

        entries = entries_by_name.get(spec.name, {})
        actual_isr = entries.get("min.insync.replicas", "?")
        if actual_isr == "?" or int(actual_isr) < spec.min_insync_replicas:
            problems.append(
                TopicProblem(
                    spec.name,
                    "min.insync.replicas",
                    str(spec.min_insync_replicas),
                    str(actual_isr),
                )
            )

        unclean = entries.get("unclean.leader.election.enable", "?")
        if unclean != "false":
            problems.append(
                TopicProblem(spec.name, "unclean.leader.election.enable", "false", str(unclean))
            )

    return problems


async def ensure_topics(admin: _AdminClient, specs: Sequence[TopicSpec]) -> None:
    """Create any missing topic with the right settings from the start.

    Explicit creation rather than relying on ``auto.create.topics.enable``:
    an auto-created topic gets broker defaults, which are exactly the unsafe
    ones this module exists to avoid.
    """
    from aiokafka.admin import NewTopic

    await admin.create_topics(
        [
            NewTopic(
                spec.name,
                num_partitions=spec.partitions,
                replication_factor=spec.replication_factor,
                topic_configs=spec.topic_configs(),
            )
            for spec in specs
        ]
    )


def require_durable_topics(problems: Sequence[TopicProblem], *, environment: str) -> None:
    """Refuse to start in production when durability is not actually configured.

    Environment-aware because a single-broker dev stack cannot satisfy
    ``replication_factor=3`` and demanding it there would only teach everyone
    to ignore the check. In production the same finding is fatal: a service
    that starts and quietly loses acknowledged writes is worse than one that
    does not start.
    """
    if not problems:
        return

    listing = "; ".join(str(problem) for problem in problems)
    if environment == "production":
        raise ServiceUnavailableError(
            "Kafka topics are not configured for durable writes.",
            context={"problems": listing},
        )
    logger.warning("Kafka topic durability is below production settings", problems=listing)

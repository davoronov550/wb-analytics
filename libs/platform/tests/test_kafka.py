"""Tests for the Kafka producer and consumer (T018).

The contract under test: no message is lost and none is processed twice by
accident, at any of the points where Kafka lets that happen.

The first version of this module failed the first half. It claimed the
``event_id`` *before* running the handler, so a redelivery after a handler
failure was skipped as a duplicate — the message was delivered and never
processed, which is precisely the loss the commit order exists to prevent. The
defence being traded away for it (two consumers handling one event at once)
barely exists: Kafka already assigns a partition to one consumer per group, so
the overlap is confined to a rebalance window.

``TestNoSilentLoss`` is the regression suite for that mistake.
"""

from __future__ import annotations

from typing import Any

import pytest

from wb_platform.config import Environment, LogLevel, ObservabilitySettings, ServiceSettings
from wb_platform.errors import ServiceUnavailableError
from wb_platform.kafka import (
    EventConsumer,
    EventProducer,
    InboundMessage,
    Outcome,
    RedisDedupStore,
    TopicProblem,
    TopicSpec,
    consumer_config,
    dlq_topic,
    ensure_topics,
    producer_config,
    require_durable_topics,
    verify_topics,
)
from wb_platform.otel import configure_tracing, current_trace_id, shutdown_tracing, traced


@pytest.fixture(autouse=True)
def tracing() -> Any:
    configure_tracing(
        ServiceSettings(
            service_name="catalog", environment=Environment.PRODUCTION, log_level=LogLevel.INFO
        ),
        ObservabilitySettings(),
    )
    yield
    shutdown_tracing()


class _FakeProducer:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send_and_wait(
        self, topic: str, value: bytes, *, key: bytes | None = None, headers: Any = None
    ) -> None:
        self.sent.append(
            {"topic": topic, "value": value, "key": key, "headers": list(headers or [])}
        )


class _MemoryDedup:
    def __init__(self) -> None:
        self.processed: set[str] = set()
        self.attempts: dict[str, int] = {}

    async def is_processed(self, event_id: str) -> bool:
        return event_id in self.processed

    async def mark_processed(self, event_id: str) -> None:
        self.processed.add(event_id)

    async def record_attempt(self, event_id: str) -> int:
        self.attempts[event_id] = self.attempts.get(event_id, 0) + 1
        return self.attempts[event_id]

    async def forget_attempts(self, event_id: str) -> None:
        self.attempts.pop(event_id, None)


def message(
    *, event_id: str | None = "event-1", offset: int = 7, topic: str = "catalog.products.v1"
) -> InboundMessage:
    headers = [("event_id", event_id.encode())] if event_id else []
    return InboundMessage(
        topic=topic,
        partition=0,
        offset=offset,
        key=b"wb:1",
        value=b'{"query": "naushniki"}',
        headers=tuple(headers),
    )


# --------------------------------------------------------------------------
# The regression suite
# --------------------------------------------------------------------------


class TestNoSilentLoss:
    """Each case is a way a message could be delivered and never processed."""

    @pytest.mark.asyncio
    async def test_a_failed_message_is_retried_not_swallowed(self) -> None:
        """The defect this module was rewritten for.

        Claiming the id before the handler made the redelivery look like a
        duplicate, so the work was never done and nothing said so.
        """
        dedup = _MemoryDedup()
        consumer = EventConsumer(dedup=dedup, max_attempts=5)
        attempts: list[int] = []

        async def flaky(_: InboundMessage) -> None:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("downstream unavailable")

        assert await consumer.handle(message(), flaky) is Outcome.RETRY
        assert await consumer.handle(message(), flaky) is Outcome.RETRY
        assert await consumer.handle(message(), flaky) is Outcome.COMMIT
        assert len(attempts) == 3  # actually retried, not skipped

    @pytest.mark.asyncio
    async def test_a_failure_does_not_mark_the_event_processed(self) -> None:
        dedup = _MemoryDedup()
        consumer = EventConsumer(dedup=dedup)

        async def failing(_: InboundMessage) -> None:
            raise RuntimeError("boom")

        await consumer.handle(message(), failing)

        assert dedup.processed == set()

    @pytest.mark.asyncio
    async def test_success_marks_it_and_clears_the_attempt_counter(self) -> None:
        """A stale counter would send a later legitimate redelivery to the DLQ."""
        dedup = _MemoryDedup()
        consumer = EventConsumer(dedup=dedup)
        calls: list[int] = []

        async def flaky(_: InboundMessage) -> None:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("transient")

        await consumer.handle(message(), flaky)
        await consumer.handle(message(), flaky)

        assert dedup.processed == {"event-1"}
        assert dedup.attempts == {}


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_redelivery_after_success_does_not_rerun_the_handler(self) -> None:
        consumer = EventConsumer(dedup=_MemoryDedup())
        calls: list[int] = []

        async def handler(_: InboundMessage) -> None:
            calls.append(1)

        assert await consumer.handle(message(), handler) is Outcome.COMMIT
        assert await consumer.handle(message(), handler) is Outcome.COMMIT
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_distinct_events_are_both_handled(self) -> None:
        consumer = EventConsumer(dedup=_MemoryDedup())
        seen: list[str] = []

        async def handler(msg: InboundMessage) -> None:
            seen.append(str(msg.event_id))

        await consumer.handle(message(event_id="a"), handler)
        await consumer.handle(message(event_id="b"), handler)

        assert seen == ["a", "b"]

    @pytest.mark.asyncio
    async def test_dedup_is_an_optimisation_not_a_guarantee(self) -> None:
        """A crash between the handler finishing and the mark re-runs it.

        Documented rather than fixed: closing this window needs the mark and
        the handler's own writes in one transaction, which only the handler can
        do. Correctness therefore lives in the data layer — ON CONFLICT DO
        NOTHING, ReplacingMergeTree — and this dedup only saves redundant work.
        """
        dedup = _MemoryDedup()
        consumer = EventConsumer(dedup=dedup)
        calls: list[int] = []

        async def handler(_: InboundMessage) -> None:
            calls.append(1)

        await consumer.handle(message(), handler)
        dedup.processed.clear()  # the mark never reached Redis
        await consumer.handle(message(), handler)

        assert len(calls) == 2  # hence handlers must tolerate this


class TestPoisonMessages:
    @pytest.mark.asyncio
    async def test_a_message_that_always_fails_goes_to_the_dlq(self) -> None:
        """Kafka delivers a partition in order, so retrying forever stops
        every message behind this one too."""
        producer = _FakeProducer()
        consumer = EventConsumer(
            dedup=_MemoryDedup(),
            dead_letter=EventProducer(producer).dead_letter,
            max_attempts=3,
        )

        async def always_fails(_: InboundMessage) -> None:
            raise ValueError("unparseable payload")

        outcomes = [await consumer.handle(message(), always_fails) for _ in range(3)]

        assert outcomes == [Outcome.RETRY, Outcome.RETRY, Outcome.DEAD_LETTER]
        assert producer.sent[0]["topic"] == "catalog.products.v1.dlq"

    @pytest.mark.asyncio
    async def test_dlq_entry_records_why_and_from_where(self) -> None:
        producer = _FakeProducer()
        consumer = EventConsumer(
            dedup=_MemoryDedup(), dead_letter=EventProducer(producer).dead_letter, max_attempts=1
        )

        async def always_fails(_: InboundMessage) -> None:
            raise ValueError("unparseable payload")

        await consumer.handle(message(offset=42), always_fails)

        headers = dict(producer.sent[0]["headers"])
        assert b"unparseable payload" in headers["dlq_reason"]
        assert headers["dlq_source_topic"] == b"catalog.products.v1"
        assert b'"offset": 42' in headers["dlq_source_offset"]

    @pytest.mark.asyncio
    async def test_dlq_entry_keeps_the_trace_context(self) -> None:
        """A dead-lettered message must still join the trace that produced it."""
        producer = _FakeProducer()
        with traced("publish"):
            expected = current_trace_id()
            await EventProducer(producer).publish("t", key="k", payload=b"{}")

        original = InboundMessage(
            topic="t",
            partition=0,
            offset=1,
            key=b"k",
            value=b"{}",
            headers=tuple(producer.sent[0]["headers"]),
        )
        await EventProducer(producer).dead_letter(original, "boom")

        assert "traceparent" in dict(producer.sent[1]["headers"])
        assert expected is not None

    @pytest.mark.asyncio
    async def test_message_without_an_event_id_is_dead_lettered(self) -> None:
        """Retrying cannot grow the header, so retrying loops forever."""
        producer = _FakeProducer()
        consumer = EventConsumer(
            dedup=_MemoryDedup(), dead_letter=EventProducer(producer).dead_letter
        )

        async def handler(_: InboundMessage) -> None:
            return None

        assert await consumer.handle(message(event_id=None), handler) is Outcome.DEAD_LETTER
        assert b"missing event_id" in dict(producer.sent[0]["headers"])["dlq_reason"]

    @pytest.mark.asyncio
    async def test_without_a_sink_the_partition_stalls_rather_than_dropping(self) -> None:
        """Halting is louder than dropping, and shows up in consumer lag."""
        consumer = EventConsumer(dedup=_MemoryDedup(), dead_letter=None, max_attempts=1)

        async def always_fails(_: InboundMessage) -> None:
            raise ValueError("boom")

        assert await consumer.handle(message(), always_fails) is Outcome.RETRY


class TestCommitOrder:
    @pytest.mark.asyncio
    async def test_failing_handler_does_not_allow_a_commit(self) -> None:
        consumer = EventConsumer(dedup=_MemoryDedup())

        async def handler(_: InboundMessage) -> None:
            raise RuntimeError("downstream unavailable")

        assert await consumer.handle(message(), handler) is Outcome.RETRY

    @pytest.mark.asyncio
    async def test_successful_handler_allows_a_commit(self) -> None:
        consumer = EventConsumer(dedup=_MemoryDedup())

        async def handler(_: InboundMessage) -> None:
            return None

        assert await consumer.handle(message(), handler) is Outcome.COMMIT


class TestBrokerSettings:
    def test_producer_waits_for_every_in_sync_replica(self) -> None:
        """acks=1 loses records the producer was told were written."""
        assert producer_config()["acks"] == "all"

    def test_producer_deduplicates_its_own_retries(self) -> None:
        """A retry after a lost ack would otherwise append the record twice."""
        assert producer_config()["enable_idempotence"] is True

    def test_consumer_never_commits_on_a_timer(self) -> None:
        assert consumer_config(group_id="analytics")["enable_auto_commit"] is False

    def test_a_new_group_reads_from_the_beginning(self) -> None:
        """aiokafka defaults to 'latest', which silently skips the backlog."""
        assert consumer_config(group_id="analytics")["auto_offset_reset"] == "earliest"

    def test_overrides_are_possible_but_not_the_default(self) -> None:
        assert producer_config(acks=1)["acks"] == 1


class TestProducer:
    @pytest.mark.asyncio
    async def test_attaches_an_event_id(self) -> None:
        producer = _FakeProducer()

        identifier = await EventProducer(producer).publish("t", key="wb:1", payload=b"{}")

        assert dict(producer.sent[0]["headers"])["event_id"].decode() == identifier

    @pytest.mark.asyncio
    async def test_event_id_is_a_header_not_the_payload(self) -> None:
        producer = _FakeProducer()

        await EventProducer(producer).publish("t", key="k", payload=b'{"a":1}')

        assert producer.sent[0]["value"] == b'{"a":1}'

    @pytest.mark.asyncio
    async def test_trace_context_rides_along(self) -> None:
        producer = _FakeProducer()

        with traced("request"):
            await EventProducer(producer).publish("t", key="k", payload=b"{}")

        assert "traceparent" in dict(producer.sent[0]["headers"])

    @pytest.mark.asyncio
    async def test_partition_key_is_encoded(self) -> None:
        """Ordering is per key; an unset key scatters one product's events."""
        producer = _FakeProducer()

        await EventProducer(producer).publish("t", key="wb:12345", payload=b"{}")

        assert producer.sent[0]["key"] == b"wb:12345"


class TestDlqTopicNaming:
    def test_suffix_is_predictable(self) -> None:
        assert dlq_topic("catalog.products.collected.v1") == "catalog.products.collected.v1.dlq"


class TestRedisDedupStore:
    @pytest.mark.asyncio
    async def test_marks_and_reports(self) -> None:
        class _Redis:
            def __init__(self) -> None:
                self.keys: dict[str, int] = {}

            async def exists(self, name: str) -> int:
                return int(name in self.keys)

            async def set(self, name: str, value: str, *, ex: int) -> bool:
                self.keys[name] = 1
                return True

            async def incr(self, name: str) -> int:
                self.keys[name] = self.keys.get(name, 0) + 1
                return self.keys[name]

            async def expire(self, name: str, seconds: int) -> bool:
                return True

            async def delete(self, name: str) -> int:
                return int(self.keys.pop(name, None) is not None)

        store = RedisDedupStore(_Redis(), namespace="analytics")

        assert await store.is_processed("e1") is False
        await store.mark_processed("e1")
        assert await store.is_processed("e1") is True

        assert await store.record_attempt("e2") == 1
        assert await store.record_attempt("e2") == 2
        await store.forget_attempts("e2")
        assert await store.record_attempt("e2") == 1


# --------------------------------------------------------------------------
# Topic durability
# --------------------------------------------------------------------------


class _FakeAdmin:
    """A broker whose topic configuration the test dictates."""

    def __init__(self, *, replicas: int, min_isr: str, unclean: str = "false") -> None:
        self.replicas = replicas
        self.min_isr = min_isr
        self.unclean = unclean
        self.created: list[Any] = []

    async def describe_topics(self, topics: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "topic": name,
                "error_code": 0,
                "partitions": [
                    {"partition": 0, "replicas": list(range(self.replicas)), "isr": [0]}
                ],
            }
            for name in topics
        ]

    async def describe_configs(self, resources: list[Any]) -> list[Any]:
        entries = [
            ("min.insync.replicas", self.min_isr),
            ("unclean.leader.election.enable", self.unclean),
        ]

        class _Response:
            def __init__(self) -> None:
                self.resources = [(0, "", 0, "", entries)]

        return [_Response() for _ in resources]

    async def create_topics(self, new_topics: list[Any]) -> None:
        self.created.extend(new_topics)


SPEC = TopicSpec(name="catalog.products.collected.v1")


class TestTopicDurability:
    """`acks=all` is meaningless unless the topic agrees, so the topic is checked."""

    @pytest.mark.asyncio
    async def test_correctly_configured_topic_has_no_problems(self) -> None:
        admin = _FakeAdmin(replicas=3, min_isr="2")

        assert await verify_topics(admin, [SPEC]) == []

    @pytest.mark.asyncio
    async def test_min_insync_replicas_of_one_is_reported(self) -> None:
        """The setting that silently turns acks=all into acks=1.

        "All in-sync replicas" is satisfied by the leader alone, so an
        acknowledged write can still vanish with that leader. Setting acks
        without this is not a partial guarantee — it is none.
        """
        admin = _FakeAdmin(replicas=3, min_isr="1")

        (problem,) = await verify_topics(admin, [SPEC])

        assert problem.setting == "min.insync.replicas"
        assert problem.actual == "1"

    @pytest.mark.asyncio
    async def test_insufficient_replication_factor_is_reported(self) -> None:
        admin = _FakeAdmin(replicas=1, min_isr="2")

        settings = {p.setting for p in await verify_topics(admin, [SPEC])}

        assert "replication.factor" in settings

    @pytest.mark.asyncio
    async def test_unclean_leader_election_is_reported(self) -> None:
        """Promoting a lagging replica trades a brief outage for lost data."""
        admin = _FakeAdmin(replicas=3, min_isr="2", unclean="true")

        (problem,) = await verify_topics(admin, [SPEC])

        assert problem.setting == "unclean.leader.election.enable"

    @pytest.mark.asyncio
    async def test_missing_topic_is_reported(self) -> None:
        class _Empty(_FakeAdmin):
            async def describe_topics(self, topics: list[str]) -> list[dict[str, Any]]:
                return [{"topic": name, "error_code": 3, "partitions": []} for name in topics]

        (problem,) = await verify_topics(_Empty(replicas=3, min_isr="2"), [SPEC])

        assert problem.setting == "existence"

    @pytest.mark.asyncio
    async def test_unreadable_config_response_fails_the_check(self) -> None:
        """A protocol shape change must surface as a failed check, not an
        IndexError at startup — and certainly not as a silent pass."""

        class _Broken(_FakeAdmin):
            async def describe_configs(self, resources: list[Any]) -> list[Any]:
                return [object() for _ in resources]

        settings = {
            p.setting for p in await verify_topics(_Broken(replicas=3, min_isr="2"), [SPEC])
        }

        assert "min.insync.replicas" in settings


class TestEnforcement:
    def test_production_refuses_to_start(self) -> None:
        """A service that starts and quietly loses acknowledged writes is
        worse than one that does not start."""
        problems = [TopicProblem("t", "min.insync.replicas", "2", "1")]

        with pytest.raises(ServiceUnavailableError):
            require_durable_topics(problems, environment="production")

    def test_local_only_warns(self) -> None:
        """A single-broker dev stack cannot satisfy replication_factor=3, and
        failing there would only teach everyone to ignore the check."""
        problems = [TopicProblem("t", "replication.factor", "3", "1")]

        require_durable_topics(problems, environment="local")

    def test_no_problems_passes_everywhere(self) -> None:
        require_durable_topics([], environment="production")


class TestTopicSpec:
    def test_defaults_are_the_durable_ones(self) -> None:
        configs = SPEC.topic_configs()

        assert configs["min.insync.replicas"] == "2"
        assert configs["unclean.leader.election.enable"] == "false"

    @pytest.mark.asyncio
    async def test_topics_are_created_explicitly_not_auto(self) -> None:
        """An auto-created topic gets broker defaults — the unsafe ones."""
        admin = _FakeAdmin(replicas=3, min_isr="2")

        await ensure_topics(admin, [SPEC])

        assert len(admin.created) == 1

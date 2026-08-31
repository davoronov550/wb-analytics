"""Tests for the Kafka producer and consumer (T018).

Two contracts under test: a redelivered message does not run the handler twice,
and a failing handler does not move the offset.

They are one design. Committing after processing turns a crash into a
redelivery instead of a silent loss — but only if redelivery is harmless, which
is what the dedup provides. Either half alone is worse than neither: dedup
without the commit order still loses events, and the commit order without dedup
double-charges every retry.
"""

from __future__ import annotations

from typing import Any

import pytest

from wb_platform.config import Environment, LogLevel, ObservabilitySettings, ServiceSettings
from wb_platform.kafka import EventConsumer, EventProducer, InboundMessage, RedisDedupStore
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
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: Any = None,
    ) -> None:
        self.sent.append(
            {"topic": topic, "value": value, "key": key, "headers": list(headers or [])}
        )


class _MemoryDedup:
    def __init__(self) -> None:
        self.ids: set[str] = set()

    async def seen(self, event_id: str) -> bool:
        already = event_id in self.ids
        self.ids.add(event_id)
        return already


def message(
    *,
    event_id: str | None = "event-1",
    headers: list[tuple[str, bytes]] | None = None,
    offset: int = 7,
) -> InboundMessage:
    all_headers = list(headers or [])
    if event_id is not None:
        all_headers.append(("event_id", event_id.encode()))
    return InboundMessage(
        topic="catalog.products.collected.v1",
        partition=0,
        offset=offset,
        key=b"wb:1",
        value=b'{"query": "naushniki"}',
        headers=tuple(all_headers),
    )


class TestProducer:
    @pytest.mark.asyncio
    async def test_attaches_an_event_id(self) -> None:
        producer = _FakeProducer()

        identifier = await EventProducer(producer).publish(
            "catalog.products.collected.v1", key="wb:1", payload=b"{}"
        )

        headers = dict(producer.sent[0]["headers"])
        assert headers["event_id"].decode() == identifier

    @pytest.mark.asyncio
    async def test_event_id_is_a_header_not_the_payload(self) -> None:
        """A consumer must be able to deduplicate without deserialising —
        including when the schema it would need is one it cannot read."""
        producer = _FakeProducer()

        await EventProducer(producer).publish("t", key="k", payload=b'{"a":1}')

        assert producer.sent[0]["value"] == b'{"a":1}'
        assert "event_id" in dict(producer.sent[0]["headers"])

    @pytest.mark.asyncio
    async def test_trace_context_rides_along(self) -> None:
        producer = _FakeProducer()

        with traced("request"):
            expected = current_trace_id()
            await EventProducer(producer).publish("t", key="k", payload=b"{}")

        assert "traceparent" in dict(producer.sent[0]["headers"])
        assert expected is not None

    @pytest.mark.asyncio
    async def test_caller_supplied_headers_are_kept(self) -> None:
        producer = _FakeProducer()

        await EventProducer(producer).publish(
            "t", key="k", payload=b"{}", headers=[("schema", b"1")]
        )

        assert dict(producer.sent[0]["headers"])["schema"] == b"1"

    @pytest.mark.asyncio
    async def test_partition_key_is_encoded(self) -> None:
        """Ordering is per key; an unset key would scatter one product's events."""
        producer = _FakeProducer()

        await EventProducer(producer).publish("t", key="wb:12345", payload=b"{}")

        assert producer.sent[0]["key"] == b"wb:12345"


class TestDeduplication:
    @pytest.mark.asyncio
    async def test_redelivered_message_does_not_run_the_handler_twice(self) -> None:
        """At-least-once means this happens after every crash and rebalance."""
        consumer = EventConsumer(dedup=_MemoryDedup())
        calls: list[int] = []

        async def handler(_: InboundMessage) -> None:
            calls.append(1)

        assert await consumer.handle(message(), handler) is True
        assert await consumer.handle(message(), handler) is True  # same event_id
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_distinct_events_are_both_handled(self) -> None:
        consumer = EventConsumer(dedup=_MemoryDedup())
        calls: list[str] = []

        async def handler(msg: InboundMessage) -> None:
            calls.append(str(msg.event_id))

        await consumer.handle(message(event_id="a"), handler)
        await consumer.handle(message(event_id="b"), handler)

        assert calls == ["a", "b"]

    @pytest.mark.asyncio
    async def test_duplicate_is_committed_not_retried(self) -> None:
        """Returning False would replay the duplicate forever."""
        consumer = EventConsumer(dedup=_MemoryDedup())

        async def handler(_: InboundMessage) -> None:
            return None

        await consumer.handle(message(), handler)

        assert await consumer.handle(message(), handler) is True

    @pytest.mark.asyncio
    async def test_without_a_dedup_store_every_message_is_handled(self) -> None:
        consumer = EventConsumer(dedup=None)
        calls: list[int] = []

        async def handler(_: InboundMessage) -> None:
            calls.append(1)

        await consumer.handle(message(), handler)
        await consumer.handle(message(), handler)

        assert len(calls) == 2


class TestCommitOrder:
    @pytest.mark.asyncio
    async def test_failing_handler_does_not_allow_a_commit(self) -> None:
        """The offset must stay put so the message comes back.

        A lost event is invisible; a redelivered one is absorbed by the dedup.
        """
        consumer = EventConsumer(dedup=_MemoryDedup())

        async def handler(_: InboundMessage) -> None:
            raise RuntimeError("downstream unavailable")

        assert await consumer.handle(message(), handler) is False

    @pytest.mark.asyncio
    async def test_successful_handler_allows_a_commit(self) -> None:
        consumer = EventConsumer(dedup=_MemoryDedup())

        async def handler(_: InboundMessage) -> None:
            return None

        assert await consumer.handle(message(), handler) is True

    @pytest.mark.asyncio
    async def test_a_failure_still_marks_the_event_as_seen(self) -> None:
        """Known limitation, recorded deliberately.

        The dedup claim happens before the handler, so a redelivery after a
        failure is skipped rather than retried. Retrying instead would require
        releasing the claim on failure — which reopens the window where two
        consumers process the same event concurrently. Handlers that must
        survive their own failures need their own retry, not this one.
        """
        dedup = _MemoryDedup()
        consumer = EventConsumer(dedup=dedup)
        calls: list[int] = []

        async def failing(_: InboundMessage) -> None:
            calls.append(1)
            raise RuntimeError("boom")

        assert await consumer.handle(message(), failing) is False
        assert await consumer.handle(message(), failing) is True  # skipped as duplicate
        assert len(calls) == 1


class TestTracePropagation:
    @pytest.mark.asyncio
    async def test_consumer_continues_the_producer_trace(self) -> None:
        producer = _FakeProducer()
        with traced("request"):
            produced = current_trace_id()
            await EventProducer(producer).publish("t", key="k", payload=b"{}")

        headers = [(name, value) for name, value in producer.sent[0]["headers"]]
        seen: list[str | None] = []

        async def handler(_: InboundMessage) -> None:
            seen.append(current_trace_id())

        await EventConsumer(dedup=_MemoryDedup()).handle(
            InboundMessage(
                topic="t", partition=0, offset=1, key=b"k", value=b"{}", headers=tuple(headers)
            ),
            handler,
        )

        assert seen == [produced]


class TestMissingEventId:
    @pytest.mark.asyncio
    async def test_message_without_an_id_is_skipped_not_retried(self) -> None:
        """Redelivery will not grow the header, so retrying loops forever."""
        consumer = EventConsumer(dedup=_MemoryDedup(), require_event_id=True)
        calls: list[int] = []

        async def handler(_: InboundMessage) -> None:
            calls.append(1)

        assert await consumer.handle(message(event_id=None), handler) is True
        assert calls == []

    @pytest.mark.asyncio
    async def test_can_be_relaxed_for_third_party_topics(self) -> None:
        consumer = EventConsumer(dedup=None, require_event_id=False)
        calls: list[int] = []

        async def handler(_: InboundMessage) -> None:
            calls.append(1)

        assert await consumer.handle(message(event_id=None), handler) is True
        assert calls == [1]


class TestRedisDedupStore:
    @pytest.mark.asyncio
    async def test_first_call_claims_and_second_reports_seen(self) -> None:
        class _Redis:
            def __init__(self) -> None:
                self.keys: set[str] = set()

            async def set(self, name: str, value: str, *, ex: int, nx: bool) -> bool | None:
                if nx and name in self.keys:
                    return None
                self.keys.add(name)
                return True

        store = RedisDedupStore(_Redis(), namespace="analytics")

        assert await store.seen("event-1") is False
        assert await store.seen("event-1") is True

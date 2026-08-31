"""Tests for the transactional outbox (T016).

The contract under test: killing the process between the commit and the publish
does not lose the event.

That failure exists in the code today. ``CollectProducts`` upserts products and
then publishes ``ProductsCollected``; a crash in between loses the event, and
with it the price snapshot and any alert it would have fired. Nothing reports
it — the collection looks successful.

Integration tests need PostgreSQL: ``FOR UPDATE SKIP LOCKED`` and transaction
atomicity have no meaningful stand-in, and a fake that "implements" them would
only be testing the fake.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wb_platform.config import DatabaseSettings
from wb_platform.db import create_engine, create_session_factory
from wb_platform.outbox import (
    OutboxMessage,
    OutboxRelay,
    claim_unpublished,
    enqueue,
    mark_published,
    outbox_metadata,
    outbox_table,
)

DSN = os.environ.get(
    "TEST_DATABASE_DSN", "postgresql+asyncpg://wb_app:wbapp@127.0.0.1:15432/wb_catalog"
)


# --------------------------------------------------------------------------
# Relay logic — no database needed
# --------------------------------------------------------------------------


class _RecordingPublisher:
    def __init__(self, fail_at: int | None = None) -> None:
        self.published: list[OutboxMessage] = []
        self._fail_at = fail_at

    async def publish(self, message: OutboxMessage) -> None:
        if self._fail_at is not None and len(self.published) == self._fail_at:
            raise ConnectionError("broker unavailable")
        self.published.append(message)


def _message(index: int) -> OutboxMessage:
    return OutboxMessage(
        id=index,
        event_id=f"event-{index}",
        topic="catalog.products.collected.v1",
        partition_key="wb:1",
        payload=b"{}",
    )


class _FakeSession:
    """Captures what the relay asked the database to do."""

    def __init__(self, messages: list[OutboxMessage]) -> None:
        self.messages = messages
        self.marked: list[int] = []

    async def execute(self, statement: Any) -> Any:  # pragma: no cover - unused path
        raise AssertionError("the relay should go through the helpers")


class TestRelayOrdering:
    @pytest.mark.asyncio
    async def test_publishes_then_marks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Publish first, mark second — never the reverse.

        Marking first loses events on a crash in between: the row reads as
        delivered while the broker never saw it, which is the exact failure the
        outbox exists to prevent. This order can only *re-deliver*, and
        re-delivery is what consumers are built to tolerate.
        """
        order: list[str] = []
        messages = [_message(1), _message(2)]
        publisher = _RecordingPublisher()

        async def fake_claim(session: Any, *, limit: int) -> list[OutboxMessage]:
            return messages

        async def fake_mark(session: Any, ids: Any, *, now: Any = None) -> None:
            order.append(f"mark:{list(ids)}")

        original_publish = publisher.publish

        async def tracked(message: OutboxMessage) -> None:
            order.append(f"publish:{message.id}")
            await original_publish(message)

        monkeypatch.setattr("wb_platform.outbox.claim_unpublished", fake_claim)
        monkeypatch.setattr("wb_platform.outbox.mark_published", fake_mark)
        publisher.publish = tracked  # type: ignore[method-assign]

        sent = await OutboxRelay(publisher).run_once(_FakeSession(messages))  # type: ignore[arg-type]

        assert sent == 2
        assert order == ["publish:1", "publish:2", "mark:[1, 2]"]

    @pytest.mark.asyncio
    async def test_stops_at_the_first_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Skipping past a failure would reorder events for that key."""
        messages = [_message(1), _message(2), _message(3)]
        publisher = _RecordingPublisher(fail_at=1)
        marked: list[list[int]] = []

        async def fake_claim(session: Any, *, limit: int) -> list[OutboxMessage]:
            return messages

        async def fake_mark(session: Any, ids: Any, *, now: Any = None) -> None:
            marked.append(list(ids))

        monkeypatch.setattr("wb_platform.outbox.claim_unpublished", fake_claim)
        monkeypatch.setattr("wb_platform.outbox.mark_published", fake_mark)

        sent = await OutboxRelay(publisher).run_once(_FakeSession(messages))  # type: ignore[arg-type]

        assert sent == 1
        assert [m.id for m in publisher.published] == [1]
        assert marked == [[1]]  # the failed one stays unpublished for the next pass

    @pytest.mark.asyncio
    async def test_empty_outbox_is_a_no_op(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_claim(session: Any, *, limit: int) -> list[OutboxMessage]:
            return []

        monkeypatch.setattr("wb_platform.outbox.claim_unpublished", fake_claim)

        assert await OutboxRelay(_RecordingPublisher()).run_once(_FakeSession([])) == 0  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Against real PostgreSQL
# --------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[Any]:
    engine = create_engine(DatabaseSettings(dsn=DSN))
    async with engine.begin() as connection:
        await connection.run_sync(outbox_metadata.drop_all)
        await connection.run_sync(outbox_metadata.create_all)
    yield create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(outbox_metadata.drop_all)
    await engine.dispose()


async def _count_unpublished(session: AsyncSession) -> int:
    rows = await session.execute(
        select(outbox_table.c.id).where(outbox_table.c.published_at.is_(None))
    )
    return len(rows.all())


@pytest.mark.integration
class TestAtomicity:
    @pytest.mark.asyncio
    async def test_event_and_data_share_one_transaction(self, session_factory: Any) -> None:
        """The DoD: a crash after the commit cannot lose the event.

        Simulated the only way that is meaningful — commit the transaction,
        then never publish. The event is still in the table for the relay to
        find, which is precisely what today's publish-after-commit cannot say.
        """
        async with session_factory() as session:
            await enqueue(
                session,
                topic="catalog.products.collected.v1",
                partition_key="wb:1",
                payload=b'{"query": "naushniki"}',
            )
            await session.commit()

        # …process dies here, before anything reaches the broker.

        async with session_factory() as session:
            assert await _count_unpublished(session) == 1

    @pytest.mark.asyncio
    async def test_rollback_discards_the_event_with_the_data(self, session_factory: Any) -> None:
        """The other half of atomicity: no event for work that did not happen."""
        async with session_factory() as session:
            await enqueue(session, topic="t", partition_key="k", payload=b"{}")
            await session.rollback()

        async with session_factory() as session:
            assert await _count_unpublished(session) == 0


@pytest.mark.integration
class TestConcurrentRelays:
    @pytest.mark.asyncio
    async def test_two_relays_never_claim_the_same_row(self, session_factory: Any) -> None:
        """`FOR UPDATE SKIP LOCKED` is what makes replicas safe.

        Plain `FOR UPDATE` would serialise them; no lock at all would have both
        publish the same events.
        """
        async with session_factory() as session:
            for index in range(6):
                await enqueue(session, topic="t", partition_key=f"k{index}", payload=b"{}")
            await session.commit()

        first = session_factory()
        second = session_factory()
        try:
            claimed_first = await claim_unpublished(first, limit=3)
            claimed_second = await claim_unpublished(second, limit=3)

            ids_first = {m.id for m in claimed_first}
            ids_second = {m.id for m in claimed_second}

            assert len(ids_first) == 3
            assert len(ids_second) == 3
            assert ids_first.isdisjoint(ids_second)
        finally:
            await first.rollback()
            await second.rollback()
            await first.close()
            await second.close()


@pytest.mark.integration
class TestPersistence:
    @pytest.mark.asyncio
    async def test_events_leave_in_the_order_they_were_written(self, session_factory: Any) -> None:
        """Kafka guarantees order per partition key; the outbox must not undo it."""
        async with session_factory() as session:
            for index in range(5):
                await enqueue(
                    session, topic="t", partition_key="same-key", payload=str(index).encode()
                )
            await session.commit()

        async with session_factory() as session:
            claimed = await claim_unpublished(session, limit=10)

        assert [m.payload for m in claimed] == [b"0", b"1", b"2", b"3", b"4"]

    @pytest.mark.asyncio
    async def test_marked_events_are_not_claimed_again(self, session_factory: Any) -> None:
        async with session_factory() as session:
            await enqueue(session, topic="t", partition_key="k", payload=b"{}")
            await session.commit()

        async with session_factory() as session:
            claimed = await claim_unpublished(session)
            await mark_published(session, [m.id for m in claimed])
            await session.commit()

        async with session_factory() as session:
            assert await claim_unpublished(session) == []

    @pytest.mark.asyncio
    async def test_headers_survive_the_round_trip(self, session_factory: Any) -> None:
        """The trace context rides in headers — losing it breaks the trace."""
        async with session_factory() as session:
            await enqueue(
                session,
                topic="t",
                partition_key="k",
                payload=b"{}",
                headers={"traceparent": "00-abc-def-01"},
            )
            await session.commit()

        async with session_factory() as session:
            (message,) = await claim_unpublished(session)

        assert message.headers == {"traceparent": "00-abc-def-01"}

    @pytest.mark.asyncio
    async def test_event_id_is_generated_when_not_supplied(self, session_factory: Any) -> None:
        """Consumers deduplicate on it, so it cannot be optional in the row."""
        async with session_factory() as session:
            generated = await enqueue(session, topic="t", partition_key="k", payload=b"{}")
            await session.commit()

        async with session_factory() as session:
            (message,) = await claim_unpublished(session)

        assert message.event_id == generated
        assert len(generated) == 36  # uuid4

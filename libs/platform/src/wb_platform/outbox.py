"""Transactional outbox shared by every service (T016).

Fixes a defect that exists in the code today. ``CollectProducts`` upserts
products and then publishes ``ProductsCollected``; a crash between the two
loses the event, and with it the price snapshot and any alert it would have
fired. Nothing reports the loss — the collection looks successful.

The outbox removes the gap: the event is written **in the same transaction** as
the data, so either both land or neither does. A separate relay then publishes
what the table holds. Delivery becomes at-least-once rather than at-most-once,
which is why every consumer must be idempotent (T018).

Claiming rows with ``FOR UPDATE SKIP LOCKED`` is what lets several relay
replicas run at once: each takes rows the others have not, with no coordination
and no duplicate publishing.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    LargeBinary,
    MetaData,
    String,
    Table,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "OutboxMessage",
    "OutboxRelay",
    "Publisher",
    "claim_unpublished",
    "enqueue",
    "outbox_metadata",
    "outbox_table",
]

#: Rows claimed per relay pass. Large enough to amortise the round trip, small
#: enough that a crash re-delivers a bounded number of already-published events.
DEFAULT_BATCH_SIZE: Final = 100

outbox_metadata = MetaData()

#: The table every service owning a PostgreSQL database must create. Defined
#: here rather than copied into nine Alembic migrations, so the relay can rely
#: on one shape.
outbox_table = Table(
    "outbox",
    outbox_metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("event_id", String(36), nullable=False, unique=True),
    Column("topic", String(255), nullable=False),
    # Kafka partitions by key, so ordering is guaranteed per key and nowhere
    # else. For product events this is `marketplace:external_id`.
    Column("partition_key", String(255), nullable=False),
    Column("payload", LargeBinary, nullable=False),
    Column("headers", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=True),
    # Partial index: the relay only ever reads unpublished rows, and once the
    # table holds millions of delivered events a full index would be mostly
    # dead weight.
    Index("ix_outbox_unpublished", "id", postgresql_where=text("published_at IS NULL")),
)


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """One event awaiting publication."""

    id: int
    event_id: str
    topic: str
    partition_key: str
    payload: bytes
    headers: dict[str, str] = field(default_factory=dict)


class Publisher:
    """What the relay needs from a message broker."""

    async def publish(self, message: OutboxMessage) -> None:  # pragma: no cover - protocol
        raise NotImplementedError


async def enqueue(
    session: AsyncSession,
    *,
    topic: str,
    partition_key: str,
    payload: bytes,
    headers: dict[str, str] | None = None,
    event_id: str | None = None,
    now: datetime | None = None,
) -> str:
    """Write an event inside the caller's transaction.

    Deliberately takes the caller's ``session`` and does **not** commit: the
    whole guarantee is that this insert shares a fate with the data change
    beside it. A helper that opened its own transaction would restore exactly
    the gap the outbox exists to close.
    """
    generated = event_id or str(uuid.uuid4())
    await session.execute(
        outbox_table.insert().values(
            event_id=generated,
            topic=topic,
            partition_key=partition_key,
            payload=payload,
            headers=headers or {},
            created_at=now or datetime.now(UTC),
        )
    )
    return generated


async def claim_unpublished(
    session: AsyncSession, *, limit: int = DEFAULT_BATCH_SIZE
) -> list[OutboxMessage]:
    """Take a batch of unpublished events, locking them against other relays.

    ``FOR UPDATE SKIP LOCKED`` is what makes several relay replicas safe:
    each skips rows another has claimed instead of blocking on them. Plain
    ``FOR UPDATE`` would serialise the replicas; no locking at all would have
    them publish the same events twice.

    Ordered by ``id`` so events leave in the order they were written.
    """
    rows = await session.execute(
        select(
            outbox_table.c.id,
            outbox_table.c.event_id,
            outbox_table.c.topic,
            outbox_table.c.partition_key,
            outbox_table.c.payload,
            outbox_table.c.headers,
        )
        .where(outbox_table.c.published_at.is_(None))
        .order_by(outbox_table.c.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return [
        OutboxMessage(
            id=row.id,
            event_id=row.event_id,
            topic=row.topic,
            partition_key=row.partition_key,
            payload=row.payload,
            headers=dict(row.headers or {}),
        )
        for row in rows
    ]


async def mark_published(
    session: AsyncSession, ids: Sequence[int], *, now: datetime | None = None
) -> None:
    """Stamp the rows the broker accepted."""
    if not ids:
        return
    await session.execute(
        update(outbox_table)
        .where(outbox_table.c.id.in_(list(ids)))
        .values(published_at=now or datetime.now(UTC))
    )


class OutboxRelay:
    """Publishes what the outbox holds, one batch per pass.

    Reusable rather than reimplemented per service: the ordering of publish and
    commit below is the whole correctness argument, and it is not something to
    re-derive nine times.
    """

    def __init__(
        self,
        publisher: Publisher,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._publisher = publisher
        self._batch_size = batch_size

    async def run_once(self, session: AsyncSession) -> int:
        """Publish one batch; returns how many events went out.

        Publish first, mark second. The reverse would lose events on a crash
        between the two — the row would read as delivered while the broker never
        saw it, which is the very failure the outbox exists to prevent. This
        order can instead re-deliver an event that was already published, and
        re-delivery is what consumers are built to tolerate.
        """
        messages = await claim_unpublished(session, limit=self._batch_size)
        if not messages:
            return 0

        published: list[int] = []
        for message in messages:
            # Stop at the first failure rather than skipping ahead: the rows
            # are ordered, and publishing past a failure would reorder events
            # for the key that failed.
            try:
                await self._publisher.publish(message)
            except Exception:
                break
            published.append(message.id)

        await mark_published(session, published)
        return len(published)


def outbox_ddl() -> Any:
    """The table object, for a service's Alembic migration to create."""
    return outbox_table

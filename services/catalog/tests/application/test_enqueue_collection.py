"""Use-case tests for EnqueueCollection — fake ports, no queue, no DB.

New in the migration rather than copied: the Django tree covered this use case
only through an adapter test of the task queue, so the rule that actually
matters here — a second request for a query already being collected must not
start a second run — was never asserted anywhere.

That rule is worth a test on its own. It is invisible in the happy path, it
protects against a duplicate collection run per impatient click, and in the
target it becomes the reason a retried Kafka command does not fan out into
several parse jobs.
"""

from __future__ import annotations

import pytest

from catalog.application.dto import ParseJob
from catalog.application.use_cases.enqueue_collection import (
    COLLECT_TASK_NAME,
    EnqueueCollection,
)

# Сценарии стали корутинами вместе с портами: за каждым портом стоит
# ввод-вывод. Строгий режим pytest-asyncio требует маркер явно.
pytestmark = pytest.mark.asyncio


class FakeParseJobRepository:
    """Only the two methods this use case calls; the rest raise if reached."""

    def __init__(self, active: ParseJob | None = None) -> None:
        self._active = active
        self.created: list[str] = []

    async def find_active(self, query: str) -> ParseJob | None:
        return self._active

    async def create_pending(self, query: str) -> ParseJob:
        self.created.append(query)
        return ParseJob(task_id=f"task-{len(self.created)}", query=query, status="pending")

    async def get(self, task_id: str) -> ParseJob | None:  # pragma: no cover - not used here
        raise NotImplementedError

    async def mark_running(self, task_id: str) -> None:  # pragma: no cover - not used here
        raise NotImplementedError

    async def mark_done(self, task_id: str, created: int, updated: int) -> None:
        raise NotImplementedError  # pragma: no cover - not used here

    async def mark_failed(self, task_id: str, error: str) -> None:
        raise NotImplementedError  # pragma: no cover - not used here


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict[str, object]]] = []

    async def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        self.enqueued.append((task_name, payload))
        return f"queued-{len(self.enqueued)}"


def _make(repository: FakeParseJobRepository, queue: FakeQueue) -> EnqueueCollection:
    return EnqueueCollection(repository=repository, queue=queue)


class TestFirstRequestStartsARun:
    async def test_creates_a_pending_job_and_enqueues_it(self) -> None:
        repository, queue = FakeParseJobRepository(), FakeQueue()

        job = await _make(repository, queue).execute("наушники")

        assert job.status == "pending"
        assert repository.created == ["наушники"]
        assert len(queue.enqueued) == 1

    async def test_the_payload_carries_what_the_worker_needs(self) -> None:
        """The worker receives only this dict — a missing key surfaces as a
        failed run, not as a validation error here."""
        repository, queue = FakeParseJobRepository(), FakeQueue()

        job = await _make(repository, queue).execute("наушники", max_pages=3)
        (task_name, payload) = queue.enqueued[0]

        assert task_name == COLLECT_TASK_NAME
        assert payload == {"task_id": job.task_id, "query": "наушники", "max_pages": 3}

    async def test_max_pages_is_passed_through_as_none_when_omitted(self) -> None:
        """`None` means "use the server default", resolved downstream in
        CollectProducts — so it must reach the payload rather than be dropped."""
        repository, queue = FakeParseJobRepository(), FakeQueue()

        await _make(repository, queue).execute("наушники")

        assert queue.enqueued[0][1]["max_pages"] is None


class TestASecondRequestDoesNotStartAnother:
    """The rule the Django tree never asserted."""

    def _running(self) -> ParseJob:
        return ParseJob(task_id="already-running", query="наушники", status="running")

    async def test_returns_the_job_already_in_flight(self) -> None:
        repository = FakeParseJobRepository(active=self._running())
        queue = FakeQueue()

        job = await _make(repository, queue).execute("наушники")

        assert job.task_id == "already-running"

    async def test_creates_nothing_and_enqueues_nothing(self) -> None:
        """Both halves matter: creating a row without enqueuing leaves a job
        that never runs, and enqueuing without creating runs a job nothing
        tracks. The duplicate this prevents is a second full collection of the
        same query."""
        repository = FakeParseJobRepository(active=self._running())
        queue = FakeQueue()

        await _make(repository, queue).execute("наушники")

        assert repository.created == []
        assert queue.enqueued == []

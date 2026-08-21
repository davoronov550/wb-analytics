"""Scheduling use-case tests (T060) — fakes, no DB, no Celery."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from scheduling.application.interval import parse_interval
from scheduling.application.use_cases.manage_schedules import ManageSchedules
from scheduling.application.use_cases.run_due_schedules import RunDueSchedules
from scheduling.domain.schedule import Schedule

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


class FakeScheduleRepo:
    def __init__(self, schedules=None):
        self._items = {s.id: s for s in (schedules or [])}
        self._counter = max([0, *self._items.keys()])
        self.marked: list[tuple[int, datetime]] = []

    def create(self, *, query, spec, interval_seconds, active, owner_id):
        self._counter += 1
        s = Schedule(
            id=self._counter,
            query=query,
            spec=spec,
            interval_seconds=interval_seconds,
            active=active,
            owner_id=owner_id,
        )
        self._items[s.id] = s
        return s

    def list_all(self, owner_id=None):
        return [s for s in self._items.values() if owner_id is None or s.owner_id == owner_id]

    def list_active(self):
        return [s for s in self._items.values() if s.active]

    def get(self, schedule_id):
        return self._items.get(schedule_id)

    def set_active(self, schedule_id, active):
        s = replace(self._items[schedule_id], active=active)
        self._items[schedule_id] = s
        return s

    def mark_ran(self, schedule_id, when):
        self.marked.append((schedule_id, when))
        self._items[schedule_id] = replace(self._items[schedule_id], last_run_at=when)

    def delete(self, schedule_id):
        self._items.pop(schedule_id, None)


class FakeEnqueuer:
    def __init__(self):
        self.calls: list[tuple[str, int | None]] = []

    def enqueue(self, query, max_pages=None):
        self.calls.append((query, max_pages))


class FakeClock:
    def now(self):
        return NOW


class TestInterval:
    @pytest.mark.parametrize(
        "spec,seconds", [("every 6h", 21600), ("30m", 1800), ("45s", 45), ("2d", 172800)]
    )
    def test_parses(self, spec, seconds):
        assert parse_interval(spec) == seconds

    @pytest.mark.parametrize("bad", ["", "later", "0h", "-5m", "6 hours"])
    def test_rejects(self, bad):
        with pytest.raises(ValueError):
            parse_interval(bad)


class TestManageSchedules:
    def test_create_parses_spec_and_defaults_active(self):
        repo = FakeScheduleRepo()
        schedule = ManageSchedules(repository=repo).create(query="наушники", spec="every 6h")
        assert schedule.active is True
        assert schedule.interval_seconds == 21600

    def test_set_active_toggles(self):
        repo = FakeScheduleRepo()
        mgr = ManageSchedules(repository=repo)
        s = mgr.create(query="q", spec="1h")
        assert mgr.set_active(s.id, False).active is False
        assert repo.list_active() == []

    def test_delete(self):
        repo = FakeScheduleRepo()
        mgr = ManageSchedules(repository=repo)
        s = mgr.create(query="q", spec="1h")
        mgr.delete(s.id)
        assert repo.get(s.id) is None


class TestRunDueSchedules:
    def test_enqueues_only_due_active_schedules_and_marks_ran(self):
        repo = FakeScheduleRepo(
            [
                Schedule(id=1, query="a", spec="1h", interval_seconds=3600, active=True),
                Schedule(
                    id=2,
                    query="b",
                    spec="1h",
                    interval_seconds=3600,
                    active=True,
                    last_run_at=NOW - timedelta(minutes=10),
                ),
                Schedule(id=3, query="c", spec="1h", interval_seconds=3600, active=False),
            ]
        )
        enqueuer = FakeEnqueuer()

        count = RunDueSchedules(repository=repo, enqueuer=enqueuer, clock=FakeClock()).execute()

        assert enqueuer.calls == [("a", None)]
        assert count == 1
        assert repo.marked == [(1, NOW)]

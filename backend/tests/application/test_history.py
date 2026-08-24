"""Analytics history use-case tests — fakes, no DB."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from analytics.application.dto import SnapshotInput
from analytics.application.use_cases.history import ApplyRetention, ListHistory
from analytics.application.use_cases.record_snapshots import RecordSnapshots
from analytics.domain.snapshot import Snapshot
from shared.events import PriceChanged

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


class FakeSnapshotRepo:
    def __init__(self):
        self.items: list[Snapshot] = []

    def add(self, snapshot):
        self.items.append(snapshot)

    def last(self, wb_id):
        matches = [s for s in self.items if s.wb_id == wb_id]
        return matches[-1] if matches else None

    def list(self, wb_id, since=None):
        return [
            s for s in self.items if s.wb_id == wb_id and (since is None or s.captured_at >= since)
        ]

    def delete_older_than(self, cutoff):
        before = len(self.items)
        self.items = [s for s in self.items if s.captured_at >= cutoff]
        return before - len(self.items)


class FakeEventBus:
    def __init__(self):
        self.published = []

    def subscribe(self, event_type, handler):  # pragma: no cover
        pass

    def publish(self, event):
        self.published.append(event)


class FakeClock:
    def now(self):
        return NOW


def _item(wb_id=1, sale="60"):
    return SnapshotInput(
        wb_id=wb_id, price=Decimal("100"), sale_price=Decimal(sale), rating=Decimal("4.5")
    )


class TestRecordSnapshots:
    def test_first_snapshot_records_without_event(self):
        repo, bus = FakeSnapshotRepo(), FakeEventBus()
        RecordSnapshots(repository=repo, event_bus=bus, clock=FakeClock()).execute([_item()])
        assert len(repo.items) == 1
        assert bus.published == []

    def test_price_change_emits_price_changed(self):
        repo, bus = FakeSnapshotRepo(), FakeEventBus()
        uc = RecordSnapshots(repository=repo, event_bus=bus, clock=FakeClock())
        uc.execute([_item(sale="60")])
        uc.execute([_item(sale="50")])
        assert len(repo.items) == 2
        assert len(bus.published) == 1
        event = bus.published[0]
        assert isinstance(event, PriceChanged)
        assert event.old_sale_price == Decimal("60")
        assert event.new_sale_price == Decimal("50")

    def test_unchanged_price_emits_nothing(self):
        repo, bus = FakeSnapshotRepo(), FakeEventBus()
        uc = RecordSnapshots(repository=repo, event_bus=bus, clock=FakeClock())
        uc.execute([_item(sale="60")])
        uc.execute([_item(sale="60")])
        assert bus.published == []


def test_list_history_returns_snapshots_for_product():
    repo, bus = FakeSnapshotRepo(), FakeEventBus()
    RecordSnapshots(repository=repo, event_bus=bus, clock=FakeClock()).execute(
        [_item(wb_id=1), _item(wb_id=2)]
    )
    history = ListHistory(repository=repo).execute(1)
    assert len(history) == 1
    assert history[0].wb_id == 1


def test_apply_retention_deletes_old_snapshots():
    repo = FakeSnapshotRepo()
    repo.add(Snapshot(1, Decimal("100"), Decimal("60"), Decimal("4"), NOW - timedelta(days=40)))
    repo.add(Snapshot(1, Decimal("100"), Decimal("55"), Decimal("4"), NOW - timedelta(hours=1)))
    deleted = ApplyRetention(repository=repo, clock=FakeClock()).execute(retention_days=30)
    assert deleted == 1
    assert len(repo.items) == 1

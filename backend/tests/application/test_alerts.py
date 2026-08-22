"""Alert use-case tests (T082) — fakes, no DB, no real notifier."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from notifications.application.dto import Observation
from notifications.application.use_cases.evaluate_alerts import EvaluateAlerts
from notifications.application.use_cases.manage_alerts import ManageAlerts
from notifications.domain.alert import ABS_BELOW, EMAIL, PCT_DROP, AlertEvent, AlertRule, evaluate

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


class TestPolicy:
    def test_abs_below(self):
        rule = AlertRule(1, 1, ABS_BELOW, Decimal("100"), EMAIL, target_wb_id=1)
        assert evaluate(rule, Decimal("90"), None) is True
        assert evaluate(rule, Decimal("100"), None) is False

    def test_pct_drop(self):
        rule = AlertRule(1, 1, PCT_DROP, Decimal("15"), EMAIL, target_wb_id=1)
        assert evaluate(rule, Decimal("80"), Decimal("100")) is True  # 20% drop
        assert evaluate(rule, Decimal("90"), Decimal("100")) is False  # 10% drop
        assert evaluate(rule, Decimal("90"), None) is False  # no previous


class FakeAlertRepo:
    def __init__(self, rules):
        self._rules = rules
        self.events: list[AlertEvent] = []

    def rules_for(self, wb_id, query):
        return [
            r
            for r in self._rules
            if r.active and (r.target_wb_id == wb_id or (query and r.target_query == query))
        ]

    def last_event(self, rule_id, wb_id):
        matches = [e for e in self.events if e.rule_id == rule_id and e.wb_id == wb_id]
        return matches[-1] if matches else None

    def add_event(self, rule_id, wb_id, when):
        self.events.append(AlertEvent(rule_id=rule_id, wb_id=wb_id, triggered_at=when))


class FakeNotifier:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, channel, message):
        self.sent.append((channel, message))


class FakeClock:
    def now(self):
        return NOW


class TestEvaluateAlerts:
    def _rule(self):
        return AlertRule(1, 1, ABS_BELOW, Decimal("100"), EMAIL, target_wb_id=5)

    def test_triggers_creates_event_and_notifies(self):
        repo = FakeAlertRepo([self._rule()])
        notifier = FakeNotifier()
        count = EvaluateAlerts(repository=repo, notifier=notifier, clock=FakeClock()).execute(
            [Observation(wb_id=5, query="наушники", sale_price=Decimal("80"))]
        )
        assert count == 1
        assert len(repo.events) == 1
        assert notifier.sent[0][0] == EMAIL

    def test_no_trigger_when_condition_not_met(self):
        repo = FakeAlertRepo([self._rule()])
        notifier = FakeNotifier()
        count = EvaluateAlerts(repository=repo, notifier=notifier, clock=FakeClock()).execute(
            [Observation(wb_id=5, query="q", sale_price=Decimal("150"))]
        )
        assert count == 0
        assert notifier.sent == []

    def test_cooldown_prevents_duplicate_notifications(self):
        repo = FakeAlertRepo([self._rule()])
        repo.events.append(AlertEvent(rule_id=1, wb_id=5, triggered_at=NOW - timedelta(minutes=30)))
        notifier = FakeNotifier()
        count = EvaluateAlerts(
            repository=repo, notifier=notifier, clock=FakeClock(), cooldown_seconds=3600
        ).execute([Observation(wb_id=5, query="q", sale_price=Decimal("80"))])
        assert count == 0
        assert notifier.sent == []


class FakeCrudRepo(FakeAlertRepo):
    def __init__(self):
        super().__init__([])
        self._store = {}
        self._counter = 0

    def create(self, *, owner_id, kind, value, channel, target_wb_id, target_query):
        self._counter += 1
        rule = AlertRule(
            self._counter, owner_id, kind, value, channel, target_wb_id, target_query, True
        )
        self._store[rule.id] = rule
        return rule

    def list(self, owner_id):
        return [r for r in self._store.values() if r.owner_id == owner_id]

    def delete(self, owner_id, rule_id):
        rule = self._store.get(rule_id)
        if rule is None or rule.owner_id != owner_id:
            return False
        del self._store[rule_id]
        return True


class TestManageAlerts:
    def test_create_validates_and_is_owner_scoped(self):
        repo = FakeCrudRepo()
        mgr = ManageAlerts(repository=repo)
        mgr.create(owner_id=1, kind=ABS_BELOW, value=Decimal("100"), channel=EMAIL, target_wb_id=5)
        mgr.create(owner_id=2, kind=ABS_BELOW, value=Decimal("50"), channel=EMAIL, target_query="q")
        assert len(mgr.list(owner_id=1)) == 1
        assert len(mgr.list(owner_id=2)) == 1

    def test_create_rejects_bad_kind(self):
        with pytest.raises(ValueError):
            ManageAlerts(repository=FakeCrudRepo()).create(
                owner_id=1, kind="nope", value=Decimal("1"), channel=EMAIL, target_wb_id=5
            )

    def test_create_requires_a_target(self):
        with pytest.raises(ValueError):
            ManageAlerts(repository=FakeCrudRepo()).create(
                owner_id=1, kind=ABS_BELOW, value=Decimal("1"), channel=EMAIL
            )

    def test_delete_only_own(self):
        repo = FakeCrudRepo()
        mgr = ManageAlerts(repository=repo)
        rule = mgr.create(
            owner_id=1, kind=ABS_BELOW, value=Decimal("1"), channel=EMAIL, target_wb_id=5
        )
        assert mgr.delete(owner_id=2, rule_id=rule.id) is False
        assert mgr.delete(owner_id=1, rule_id=rule.id) is True

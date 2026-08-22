"""EvaluateAlerts use case (FE-07) — fire matching alert rules with cooldown.

Triggered from an event subscriber for each product observation. For every active
rule targeting the product (or its query) whose condition holds, records an
AlertEvent and notifies — unless a matching event fired within the cooldown
(dedup, FR-037).
"""

from __future__ import annotations

from notifications.application.dto import Observation
from notifications.application.ports import AlertRepositoryPort, NotifierPort
from notifications.domain.alert import AlertRule, evaluate
from shared.application.ports import ClockPort

_DEFAULT_COOLDOWN_SECONDS = 6 * 3600


class EvaluateAlerts:
    def __init__(
        self,
        *,
        repository: AlertRepositoryPort,
        notifier: NotifierPort,
        clock: ClockPort,
        cooldown_seconds: int = _DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self._repository = repository
        self._notifier = notifier
        self._clock = clock
        self._cooldown = cooldown_seconds

    def execute(self, observations: list[Observation]) -> int:
        now = self._clock.now()
        triggered = 0
        for obs in observations:
            for rule in self._repository.rules_for(obs.wb_id, obs.query):
                if not evaluate(rule, obs.sale_price, obs.previous_sale_price):
                    continue
                last = self._repository.last_event(rule.id, obs.wb_id)
                if last is not None and (now - last.triggered_at).total_seconds() < self._cooldown:
                    continue  # within cooldown — don't spam
                self._repository.add_event(rule.id, obs.wb_id, now)
                self._notifier.send(rule.channel, self._message(rule, obs))
                triggered += 1
        return triggered

    @staticmethod
    def _message(rule: AlertRule, obs: Observation) -> str:
        return (
            f"Alert #{rule.id}: product {obs.wb_id} sale price {obs.sale_price}₽ "
            f"({rule.kind} {rule.value})"
        )

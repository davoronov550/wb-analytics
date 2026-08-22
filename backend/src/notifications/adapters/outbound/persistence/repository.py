"""Django implementation of AlertRepositoryPort (outbound adapter)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db.models import Q

from notifications.adapters.outbound.persistence.models import AlertEventModel, AlertRuleModel
from notifications.domain.alert import AlertEvent, AlertRule


def _to_rule(model: AlertRuleModel) -> AlertRule:
    return AlertRule(
        id=model.id,
        owner_id=model.owner_id,
        kind=model.kind,
        value=model.value,
        channel=model.channel,
        target_wb_id=model.target_wb_id,
        target_query=model.target_query,
        active=model.active,
    )


class DjangoAlertRepository:
    def create(
        self, *, owner_id, kind, value: Decimal, channel, target_wb_id, target_query
    ) -> AlertRule:
        row = AlertRuleModel.objects.create(
            owner_id=owner_id,
            kind=kind,
            value=value,
            channel=channel,
            target_wb_id=target_wb_id,
            target_query=target_query,
        )
        return _to_rule(row)

    def list(self, owner_id: int) -> list[AlertRule]:
        return [_to_rule(r) for r in AlertRuleModel.objects.filter(owner_id=owner_id)]

    def get(self, owner_id: int, rule_id: int) -> AlertRule | None:
        row = AlertRuleModel.objects.filter(pk=rule_id, owner_id=owner_id).first()
        return _to_rule(row) if row else None

    def delete(self, owner_id: int, rule_id: int) -> bool:
        deleted, _ = AlertRuleModel.objects.filter(pk=rule_id, owner_id=owner_id).delete()
        return deleted > 0

    def rules_for(self, wb_id: int, query: str | None) -> list[AlertRule]:
        condition = Q(target_wb_id=wb_id)
        if query:
            condition |= Q(target_query=query)
        return [_to_rule(r) for r in AlertRuleModel.objects.filter(active=True).filter(condition)]

    def last_event(self, rule_id: int, wb_id: int) -> AlertEvent | None:
        row = (
            AlertEventModel.objects.filter(rule_id=rule_id, wb_id=wb_id)
            .order_by("-triggered_at")
            .first()
        )
        return (
            AlertEvent(rule_id=rule_id, wb_id=wb_id, triggered_at=row.triggered_at) if row else None
        )

    def add_event(self, rule_id: int, wb_id: int, when: datetime) -> None:
        AlertEventModel.objects.create(rule_id=rule_id, wb_id=wb_id, triggered_at=when)

"""ManageAlerts use case — owner-scoped CRUD over alert rules (FE-07)."""

from __future__ import annotations

from decimal import Decimal

from notifications.application.ports import AlertRepositoryPort
from notifications.domain.alert import CHANNELS, KINDS, AlertRule


class ManageAlerts:
    def __init__(self, *, repository: AlertRepositoryPort) -> None:
        self._repository = repository

    def create(
        self,
        *,
        owner_id: int,
        kind: str,
        value: Decimal,
        channel: str,
        target_wb_id: int | None = None,
        target_query: str | None = None,
    ) -> AlertRule:
        if kind not in KINDS:
            raise ValueError(f"Unknown alert kind: {kind}")
        if channel not in CHANNELS:
            raise ValueError(f"Unknown channel: {channel}")
        if target_wb_id is None and not target_query:
            raise ValueError("Alert must target a product (wb_id) or a query")
        return self._repository.create(
            owner_id=owner_id,
            kind=kind,
            value=value,
            channel=channel,
            target_wb_id=target_wb_id,
            target_query=target_query,
        )

    def list(self, owner_id: int) -> list[AlertRule]:
        return self._repository.list(owner_id)

    def delete(self, owner_id: int, rule_id: int) -> bool:
        return self._repository.delete(owner_id, rule_id)

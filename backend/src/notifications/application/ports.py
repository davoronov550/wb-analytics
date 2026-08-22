"""Notifications outbound ports."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from notifications.domain.alert import AlertEvent, AlertRule

__all__ = ["AlertRepositoryPort", "NotifierPort"]


class AlertRepositoryPort(Protocol):
    def create(
        self,
        *,
        owner_id: int,
        kind: str,
        value: Decimal,
        channel: str,
        target_wb_id: int | None,
        target_query: str | None,
    ) -> AlertRule: ...

    def list(self, owner_id: int) -> list[AlertRule]: ...

    def get(self, owner_id: int, rule_id: int) -> AlertRule | None: ...

    def delete(self, owner_id: int, rule_id: int) -> bool: ...

    def rules_for(self, wb_id: int, query: str | None) -> list[AlertRule]:
        """Active rules targeting this product id or its query."""
        ...

    def last_event(self, rule_id: int, wb_id: int) -> AlertEvent | None: ...

    def add_event(self, rule_id: int, wb_id: int, when: datetime) -> None: ...


class NotifierPort(Protocol):
    def send(self, channel: str, message: str) -> None:
        """Deliver a message via a channel (email/telegram); retries internally."""
        ...

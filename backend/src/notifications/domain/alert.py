"""Notifications domain: alert rules and the pure evaluation policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

ABS_BELOW = "abs_below"
PCT_DROP = "pct_drop"
KINDS = frozenset({ABS_BELOW, PCT_DROP})

EMAIL = "email"
TELEGRAM = "telegram"
CHANNELS = frozenset({EMAIL, TELEGRAM})


@dataclass(frozen=True)
class AlertRule:
    id: int
    owner_id: int
    kind: str
    value: Decimal
    channel: str
    target_wb_id: int | None = None
    target_query: str | None = None
    active: bool = True


@dataclass(frozen=True)
class AlertEvent:
    rule_id: int
    wb_id: int
    triggered_at: datetime


def evaluate(rule: AlertRule, current_sale: Decimal, previous_sale: Decimal | None) -> bool:
    """Whether ``rule`` fires for the given current (and previous) sale price."""
    if rule.kind == ABS_BELOW:
        return current_sale < rule.value
    if rule.kind == PCT_DROP:
        if previous_sale is None or previous_sale <= 0:
            return False
        drop_pct = (previous_sale - current_sale) / previous_sale * 100
        return drop_pct >= rule.value
    return False

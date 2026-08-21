"""Scheduling domain: a periodic collection schedule (pure — no framework)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Schedule:
    id: int
    query: str
    spec: str  # human-readable interval, e.g. "every 6h"
    interval_seconds: int
    active: bool = True
    owner_id: int | None = None
    last_run_at: datetime | None = None

    def is_due(self, now: datetime) -> bool:
        """Due when active and enough time has passed since the last run."""
        if not self.active:
            return False
        if self.last_run_at is None:
            return True
        return (now - self.last_run_at).total_seconds() >= self.interval_seconds

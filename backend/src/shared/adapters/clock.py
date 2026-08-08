"""System clock adapter (implements ClockPort).

Injected into use cases so time is a dependency, not a hidden global — keeping
time-dependent behavior deterministic under test (a fake clock replaces this).
"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

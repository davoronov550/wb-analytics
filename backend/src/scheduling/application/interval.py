"""Parse a human interval spec into seconds (boundary validation).

Accepts forms like "every 6h", "6h", "30m", "45s", "1d". Raises ValueError on
anything else so the HTTP adapter can return 400.
"""

from __future__ import annotations

import re

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_PATTERN = re.compile(r"^(?:every\s+)?(\d+)\s*([smhd])$", re.IGNORECASE)


def parse_interval(spec: str) -> int:
    match = _PATTERN.match((spec or "").strip())
    if not match:
        raise ValueError(f"Invalid interval spec: {spec!r} (expected e.g. 'every 6h', '30m')")
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError("Interval must be positive")
    return amount * _UNITS[match.group(2).lower()]

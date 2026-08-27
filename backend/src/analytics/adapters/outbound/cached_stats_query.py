"""Caching decorator for StatsQueryPort (outbound adapter).

Aggregating the whole filtered set (avg/median/stddev over every matching row) is
the most expensive read in the app, and /api/stats/ is public. This wraps any
StatsQueryPort and serves repeat requests from the cache.

It is a decorator rather than logic inside the use case on purpose: caching is
infrastructure, so it stays in the adapter layer and the use case keeps depending
only on the port.

Invalidation uses a version counter baked into the key instead of deleting keys by
pattern, because Django's built-in cache API has no pattern delete. Bumping the
version orphans every old entry at once; the orphans then expire on their own TTL.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Protocol

from analytics.application.dto import Stats
from catalog.application.dto import ProductFilter

_KEY_PREFIX = "stats"
_VERSION_KEY = f"{_KEY_PREFIX}:version"


class _Cache(Protocol):
    def get(self, key: str, default=None): ...
    def set(self, key: str, value, timeout=None) -> None: ...
    def incr(self, key: str, delta: int = 1): ...


def _normalize(value: object) -> object:
    """Make equivalent filter values produce one key.

    `Decimal("1000")` and `Decimal("1000.00")` are the same bound, and the
    repository matches `query` with `__iexact`, so casing is irrelevant too.
    Splitting the cache on those would only cost hit rate.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, str):
        return value.strip().casefold()
    return value


def stats_cache_key(filter: ProductFilter, version: int = 1) -> str:
    """Deterministic key for a filter — same filter in, same key out."""
    payload = {
        "min_price": _normalize(filter.min_price),
        "max_price": _normalize(filter.max_price),
        "min_rating": _normalize(filter.min_rating),
        "max_rating": _normalize(filter.max_rating),
        "min_reviews": _normalize(filter.min_reviews),
        "max_reviews": _normalize(filter.max_reviews),
        "query": _normalize(filter.query),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]
    return f"{_KEY_PREFIX}:v{version}:{digest}"


def _current_version(cache: _Cache) -> int:
    version = cache.get(_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(_VERSION_KEY, version, None)  # never expires
    return int(version)


def invalidate_stats_cache(cache: _Cache) -> None:
    """Orphan every cached aggregate (called after the product set changes)."""
    try:
        cache.incr(_VERSION_KEY)
    except ValueError:
        # Nothing cached yet — start the counter so the next read is a clean miss.
        cache.set(_VERSION_KEY, 2, None)


class CachedStatsQuery:
    """StatsQueryPort decorator: serve from cache, else delegate and store."""

    def __init__(self, *, inner, cache: _Cache, ttl: int) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl

    def aggregate(self, filter: ProductFilter) -> Stats:
        key = stats_cache_key(filter, _current_version(self._cache))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        computed = self._inner.aggregate(filter)
        self._cache.set(key, computed, self._ttl)
        return computed

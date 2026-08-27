"""CachedStatsQuery — the caching decorator around StatsQueryPort.

Offline: a fake inner port with a call counter and Django's local-memory cache,
so nothing here needs Redis or the database.
"""

from decimal import Decimal

import pytest
from django.core.cache import caches
from django.test import override_settings

from analytics.adapters.outbound.cached_stats_query import (
    CachedStatsQuery,
    invalidate_stats_cache,
    stats_cache_key,
)
from analytics.application.dto import Stats
from catalog.application.dto import ProductFilter


def make_stats(count: int = 1) -> Stats:
    return Stats(
        count=count,
        avg_price=Decimal("100.00"),
        median_price=Decimal("90.00"),
        price_stddev=Decimal("10.00"),
        avg_discount_abs=Decimal("5.00"),
        discount_share=0.5,
        top_by_reviews=[],
    )


class FakeStatsQuery:
    """Counts how often the expensive aggregate actually runs."""

    def __init__(self, result: Stats | None = None):
        self.calls = 0
        self._result = result or make_stats()

    def aggregate(self, filter: ProductFilter) -> Stats:
        self.calls += 1
        return self._result


@pytest.fixture
def cache():
    c = caches["default"]
    c.clear()
    yield c
    c.clear()


# --- cache key -------------------------------------------------------------


def test_same_filter_yields_the_same_key():
    a = ProductFilter(min_price=Decimal("100"), min_rating=Decimal("4"))
    b = ProductFilter(min_price=Decimal("100"), min_rating=Decimal("4"))
    assert stats_cache_key(a) == stats_cache_key(b)


def test_different_filters_yield_different_keys():
    a = ProductFilter(min_price=Decimal("100"))
    b = ProductFilter(min_price=Decimal("200"))
    assert stats_cache_key(a) != stats_cache_key(b)


def test_equivalent_decimals_normalize_to_one_key():
    """`1000` and `1000.00` are the same bound, so they must not split the cache."""
    a = ProductFilter(min_price=Decimal("1000"))
    b = ProductFilter(min_price=Decimal("1000.00"))
    assert stats_cache_key(a) == stats_cache_key(b)


def test_query_is_case_insensitive_like_the_repository_filter():
    """The repository matches the query with __iexact, so casing must not split it."""
    a = ProductFilter(query="Наушники")
    b = ProductFilter(query="наушники")
    assert stats_cache_key(a) == stats_cache_key(b)


def test_a_bound_set_to_none_differs_from_a_bound_set_to_zero():
    assert stats_cache_key(ProductFilter()) != stats_cache_key(
        ProductFilter(min_price=Decimal("0"))
    )


# --- decorator behaviour ---------------------------------------------------


def test_miss_delegates_to_the_inner_query(cache):
    inner = FakeStatsQuery()
    cached = CachedStatsQuery(inner=inner, cache=cache, ttl=60)

    result = cached.aggregate(ProductFilter())

    assert inner.calls == 1
    assert result.count == 1


def test_hit_does_not_touch_the_inner_query(cache):
    inner = FakeStatsQuery()
    cached = CachedStatsQuery(inner=inner, cache=cache, ttl=60)
    filter = ProductFilter(min_price=Decimal("10"))

    first = cached.aggregate(filter)
    second = cached.aggregate(filter)

    assert inner.calls == 1, "second call must be served from cache"
    assert first == second


def test_different_filters_are_cached_separately(cache):
    inner = FakeStatsQuery()
    cached = CachedStatsQuery(inner=inner, cache=cache, ttl=60)

    cached.aggregate(ProductFilter(min_price=Decimal("10")))
    cached.aggregate(ProductFilter(min_price=Decimal("20")))

    assert inner.calls == 2


# --- invalidation ----------------------------------------------------------


def test_invalidation_forces_a_recompute(cache):
    """A collection run changes the underlying rows, so cached aggregates must go."""
    inner = FakeStatsQuery()
    cached = CachedStatsQuery(inner=inner, cache=cache, ttl=60)
    filter = ProductFilter()

    cached.aggregate(filter)
    invalidate_stats_cache(cache)
    cached.aggregate(filter)

    assert inner.calls == 2


def test_invalidation_works_on_a_cold_cache(cache):
    """Invalidating before anything was cached must not raise."""
    invalidate_stats_cache(cache)
    inner = FakeStatsQuery()
    assert CachedStatsQuery(inner=inner, cache=cache, ttl=60).aggregate(ProductFilter())


# --- wiring ----------------------------------------------------------------


@override_settings(STATS_CACHE_TTL=0)
def test_container_returns_the_bare_query_when_caching_is_disabled():
    from analytics.adapters.outbound.stats_query import DjangoStatsQuery
    from analytics.composition import container

    assert isinstance(container.build_stats_query(), DjangoStatsQuery)


@override_settings(STATS_CACHE_TTL=120)
def test_container_wraps_the_query_when_a_ttl_is_configured():
    from analytics.composition import container

    assert isinstance(container.build_stats_query(), CachedStatsQuery)

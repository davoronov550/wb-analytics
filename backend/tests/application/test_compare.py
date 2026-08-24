"""CompareQueries use-case test — fake StatsQueryPort, no DB."""

from decimal import Decimal

from analytics.application.dto import Stats
from analytics.application.use_cases.compare_queries import CompareQueries
from catalog.application.dto import ProductFilter


class FakeStatsQuery:
    def __init__(self):
        self.filters = []
        self._n = 0

    def aggregate(self, filter):
        self.filters.append(filter)
        self._n += 1
        return Stats(
            count=self._n,
            avg_price=Decimal("0"),
            median_price=Decimal("0"),
            price_stddev=Decimal("0"),
            avg_discount_abs=Decimal("0"),
            discount_share=0.0,
            top_by_reviews=[],
        )


def test_compare_runs_aggregate_per_query_with_query_overridden():
    fake = FakeStatsQuery()
    base = ProductFilter(min_price=Decimal("100"))

    result = CompareQueries(stats_query=fake).execute(["наушники", "чайники"], base)

    assert [qs.query for qs in result] == ["наушники", "чайники"]
    # Each aggregate got the query set, base filter preserved.
    assert [f.query for f in fake.filters] == ["наушники", "чайники"]
    assert all(f.min_price == Decimal("100") for f in fake.filters)
    assert [qs.stats.count for qs in result] == [1, 2]

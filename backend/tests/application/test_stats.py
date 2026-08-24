"""ComputeStats use-case test — fake StatsQueryPort, no DB."""

from decimal import Decimal

from analytics.application.dto import Stats, TopProduct
from analytics.application.use_cases.compute_stats import ComputeStats
from catalog.application.dto import ProductFilter


class FakeStatsQuery:
    def __init__(self, stats):
        self._stats = stats
        self.calls = []

    def aggregate(self, filter):
        self.calls.append(filter)
        return self._stats


def test_compute_stats_delegates_filter_and_returns_result():
    stats = Stats(
        count=3,
        avg_price=Decimal("100.00"),
        median_price=Decimal("90.00"),
        price_stddev=Decimal("10.00"),
        avg_discount_abs=Decimal("20.00"),
        discount_share=0.66,
        top_by_reviews=[TopProduct(1, "A", 500)],
    )
    fake = FakeStatsQuery(stats)
    product_filter = ProductFilter(min_price=Decimal("50"))

    result = ComputeStats(stats_query=fake).execute(product_filter)

    assert result is stats
    assert fake.calls == [product_filter]

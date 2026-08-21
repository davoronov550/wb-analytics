"""CompareQueries use case (FE-06) — stats per query, side by side.

Reuses StatsQueryPort: for each query it aggregates with the base filter but the
query overridden, so all other filters (price/rating/reviews) apply consistently.
"""

from __future__ import annotations

from dataclasses import replace

from analytics.application.dto import QueryStats
from analytics.application.ports import StatsQueryPort
from catalog.application.dto import ProductFilter


class CompareQueries:
    def __init__(self, *, stats_query: StatsQueryPort) -> None:
        self._stats_query = stats_query

    def execute(self, queries: list[str], base_filter: ProductFilter) -> list[QueryStats]:
        return [
            QueryStats(
                query=query, stats=self._stats_query.aggregate(replace(base_filter, query=query))
            )
            for query in queries
        ]

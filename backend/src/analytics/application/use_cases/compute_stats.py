"""ComputeStats use case (FE-05) — aggregates for a filtered product set."""

from __future__ import annotations

from analytics.application.dto import Stats
from analytics.application.ports import StatsQueryPort
from catalog.application.dto import ProductFilter


class ComputeStats:
    def __init__(self, *, stats_query: StatsQueryPort) -> None:
        self._stats_query = stats_query

    def execute(self, filter: ProductFilter) -> Stats:
        return self._stats_query.aggregate(filter)

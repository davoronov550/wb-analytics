"""Analytics composition root + event subscriber registration."""

from __future__ import annotations

from analytics.adapters.outbound.catalog_reader import CatalogProductReader
from analytics.adapters.outbound.persistence.repository import DjangoSnapshotRepository
from analytics.adapters.outbound.stats_query import DjangoStatsQuery
from analytics.application.ports import ProductReaderPort, SnapshotRepositoryPort, StatsQueryPort
from analytics.application.use_cases.compare_queries import CompareQueries
from analytics.application.use_cases.compute_stats import ComputeStats
from analytics.application.use_cases.history import ApplyRetention, ListHistory
from analytics.application.use_cases.record_snapshots import RecordSnapshots
from shared.composition import get_clock, get_event_bus
from shared.events import ProductsCollected

_subscribed = False


def build_snapshot_repository() -> SnapshotRepositoryPort:
    return DjangoSnapshotRepository()


def build_product_reader() -> ProductReaderPort:
    return CatalogProductReader()


def build_record_snapshots() -> RecordSnapshots:
    return RecordSnapshots(
        repository=build_snapshot_repository(),
        event_bus=get_event_bus(),
        clock=get_clock(),
    )


def build_list_history() -> ListHistory:
    return ListHistory(repository=build_snapshot_repository())


def build_apply_retention() -> ApplyRetention:
    return ApplyRetention(repository=build_snapshot_repository(), clock=get_clock())


def build_stats_query() -> StatsQueryPort:
    return DjangoStatsQuery()


def build_compute_stats() -> ComputeStats:
    return ComputeStats(stats_query=build_stats_query())


def build_compare_queries() -> CompareQueries:
    return CompareQueries(stats_query=build_stats_query())


def _on_products_collected(event: ProductsCollected) -> None:
    items = build_product_reader().snapshot_inputs(list(event.wb_ids))
    if items:
        build_record_snapshots().execute(items)


def register_subscribers() -> None:
    """Subscribe the snapshot recorder to ProductsCollected (idempotent)."""
    global _subscribed
    if _subscribed:
        return
    get_event_bus().subscribe(ProductsCollected, _on_products_collected)
    _subscribed = True

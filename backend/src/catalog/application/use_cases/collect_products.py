"""CollectProducts use case (application) — framework-free orchestration.

Fetches raw products via the gateway, maps each to a domain Product (skipping any
that can't form a valid one — FR-005), upserts them via the repository, publishes a
ProductsCollected event, and returns a summary. Depends only on ports.
"""

from __future__ import annotations

import logging
from decimal import InvalidOperation

from catalog.application.dto import CollectInput, CollectResult, RawProduct
from catalog.application.ports.outbound import ProductRepositoryPort, WbCatalogGatewayPort
from catalog.domain.product import Product
from shared.application.ports import ClockPort, EventBusPort
from shared.domain.value_objects import Money, Rating, ReviewsCount
from shared.events import ProductsCollected

logger = logging.getLogger("catalog")


class CollectProducts:
    def __init__(
        self,
        *,
        gateway: WbCatalogGatewayPort,
        repository: ProductRepositoryPort,
        event_bus: EventBusPort,
        clock: ClockPort,
        default_max_pages: int = 10,
    ) -> None:
        self._gateway = gateway
        self._repository = repository
        self._event_bus = event_bus
        self._clock = clock
        self._default_max_pages = default_max_pages

    def execute(self, command: CollectInput) -> CollectResult:
        max_pages = command.max_pages if command.max_pages is not None else self._default_max_pages
        raws = self._gateway.fetch(command.query, max_pages)

        products = [p for p in (self._to_product(raw, command.query) for raw in raws) if p]
        result = self._repository.upsert_many(products, command.query)

        now = self._clock.now()
        self._event_bus.publish(
            ProductsCollected(
                query=command.query,
                wb_ids=tuple(p.wb_id for p in products),
                collected_count=result.collected_count,
                occurred_at=now,
            )
        )
        return CollectResult(
            query=command.query,
            collected_count=result.collected_count,
            created=result.created,
            updated=result.updated,
            finished_at=now,
        )

    def _to_product(self, raw: RawProduct, query: str) -> Product | None:
        try:
            return Product.create(
                wb_id=raw.wb_id,
                name=raw.name,
                price=Money.from_kopecks(raw.price_kopecks),
                sale_price=Money.from_kopecks(raw.sale_price_kopecks),
                rating=Rating.coerce(raw.rating),
                reviews_count=ReviewsCount.coerce(raw.reviews),
                source_query=query,
            )
        except (ValueError, TypeError, InvalidOperation) as exc:
            logger.warning("Skipping malformed WB product wb_id=%r: %s", raw.wb_id, exc)
            return None

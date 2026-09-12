"""CollectProducts use case (application) — framework-free orchestration.

Fetches raw products via the gateway, maps each to a domain Product (skipping any
that can't form a valid one), upserts them via the repository, publishes a
ProductsCollected event, and returns a summary. Depends only on ports.
"""

from __future__ import annotations

import logging
from decimal import InvalidOperation

from catalog.application.dto import CollectInput, CollectResult, RawProduct
from catalog.application.events import ProductsCollected
from catalog.application.ports.outbound import ProductRepositoryPort, WbCatalogGatewayPort
from catalog.application.ports.shared import ClockPort, EventBusPort
from catalog.domain.product import Product
from catalog.domain.value_objects import Money, Rating, ReviewsCount

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

    async def execute(self, command: CollectInput) -> CollectResult:
        max_pages = command.max_pages if command.max_pages is not None else self._default_max_pages
        raws = await self._gateway.fetch(command.query, max_pages)

        products = [p for p in (self._to_product(raw, command.query) for raw in raws) if p]
        result = await self._repository.upsert_many(products, command.query)

        now = self._clock.now()
        await self._event_bus.publish(
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
        # `RawProduct` fields are optional because Wildberries payloads are: a
        # product can arrive with no price at all. They are passed straight into
        # signatures that require a value, and the `except` below is what turns
        # that into a skip — the constructors raise on `None`, which is exactly
        # the rejection this method wants.
        #
        # `mypy --strict` is right that the call sites are off-type; the checks
        # stay as `ignore` rather than becoming explicit `is None` guards
        # because the application layer moves by copying (CLAUDE.md, п. 6), and
        # `test_maps_upserts_and_publishes_event` covers the skip.
        try:
            return Product.create(
                wb_id=raw.wb_id,  # type: ignore[arg-type]
                name=raw.name,  # type: ignore[arg-type]
                price=Money.from_kopecks(raw.price_kopecks),  # type: ignore[arg-type]
                sale_price=Money.from_kopecks(raw.sale_price_kopecks),  # type: ignore[arg-type]
                rating=Rating.coerce(raw.rating),
                reviews_count=ReviewsCount.coerce(raw.reviews),
                source_query=query,
            )
        except (ValueError, TypeError, InvalidOperation) as exc:
            logger.warning("Skipping malformed WB product wb_id=%r: %s", raw.wb_id, exc)
            return None

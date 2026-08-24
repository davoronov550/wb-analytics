"""RecordSnapshots use case — append a price snapshot per product.

Emits PriceChanged when a product's sale price differs from its previous snapshot,
so the notifications context can react (the cross-context seam).
"""

from __future__ import annotations

from analytics.application.dto import SnapshotInput
from analytics.application.ports import SnapshotRepositoryPort
from analytics.domain.snapshot import Snapshot
from shared.application.ports import ClockPort, EventBusPort
from shared.events import PriceChanged


class RecordSnapshots:
    def __init__(
        self,
        *,
        repository: SnapshotRepositoryPort,
        event_bus: EventBusPort,
        clock: ClockPort,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._clock = clock

    def execute(self, items: list[SnapshotInput]) -> int:
        now = self._clock.now()
        for item in items:
            previous = self._repository.last(item.wb_id)
            self._repository.add(
                Snapshot(
                    wb_id=item.wb_id,
                    price=item.price,
                    sale_price=item.sale_price,
                    rating=item.rating,
                    captured_at=now,
                )
            )
            if previous is not None and previous.sale_price != item.sale_price:
                self._event_bus.publish(
                    PriceChanged(
                        wb_id=item.wb_id,
                        old_sale_price=previous.sale_price,
                        new_sale_price=item.sale_price,
                        occurred_at=now,
                    )
                )
        return len(items)

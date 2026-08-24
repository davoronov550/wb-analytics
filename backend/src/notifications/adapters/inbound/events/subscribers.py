"""Event subscribers (inbound adapter) — evaluate alerts on catalog events.

PriceChanged carries old/new sale price directly (enables pct_drop). ProductsCollected
carries only ids, so current sale prices are read from the catalog to evaluate
abs_below rules. Both paths delegate to EvaluateAlerts.
"""

from __future__ import annotations

from catalog.adapters.outbound.persistence.models import ProductModel
from notifications.application.dto import Observation
from notifications.composition import container
from shared.events import PriceChanged, ProductsCollected


def on_price_changed(event: PriceChanged) -> None:
    observation = Observation(
        wb_id=event.wb_id,
        query=None,
        sale_price=event.new_sale_price,
        previous_sale_price=event.old_sale_price,
    )
    container.build_evaluate_alerts().execute([observation])


def on_products_collected(event: ProductsCollected) -> None:
    rows = ProductModel.objects.filter(wb_id__in=event.wb_ids)
    observations = [
        Observation(wb_id=row.wb_id, query=event.query, sale_price=row.sale_price) for row in rows
    ]
    if observations:
        container.build_evaluate_alerts().execute(observations)

"""Catalog composition root — the single place adapters are wired to the context.

Inbound adapters (HTTP views, CLI, Celery task) resolve their dependencies here
instead of constructing them inline (no service locator, no hidden globals). Use
cases are added as they land: CollectProducts (T027) needs the WB gateway (T026)
and task queue; ListProducts (T036) needs the repository.
"""

from __future__ import annotations

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.application.ports.outbound import ProductRepositoryPort
from shared.application.ports import ClockPort, EventBusPort
from shared.composition import get_clock, get_event_bus


def get_product_repository() -> ProductRepositoryPort:
    return DjangoProductRepository()


def get_catalog_event_bus() -> EventBusPort:
    return get_event_bus()


def get_catalog_clock() -> ClockPort:
    return get_clock()

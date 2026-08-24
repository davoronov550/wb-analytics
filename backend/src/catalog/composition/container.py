"""Catalog composition root — the single place adapters are wired to the context.

Inbound adapters (HTTP views, CLI, Celery task) resolve their dependencies here
instead of constructing them inline (no service locator, no hidden globals). Use
cases are added as they land: CollectProducts needs the WB gateway
and task queue; ListProducts needs the repository.
"""

from __future__ import annotations

from django.conf import settings

from catalog.adapters.outbound.persistence.parse_job_repository import DjangoParseJobRepository
from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.adapters.outbound.wildberries.gateway import HttpxWbCatalogGateway
from catalog.application.ports.outbound import (
    ParseJobRepositoryPort,
    ProductRepositoryPort,
    WbCatalogGatewayPort,
)
from catalog.application.use_cases.collect_products import CollectProducts
from catalog.application.use_cases.enqueue_collection import EnqueueCollection
from catalog.application.use_cases.list_products import ListProducts
from shared.adapters.task_queue import CeleryTaskQueue
from shared.application.ports import ClockPort, EventBusPort, TaskQueuePort
from shared.composition import get_clock, get_event_bus


def get_product_repository() -> ProductRepositoryPort:
    return DjangoProductRepository()


def get_catalog_event_bus() -> EventBusPort:
    return get_event_bus()


def get_catalog_clock() -> ClockPort:
    return get_clock()


def build_wb_gateway() -> WbCatalogGatewayPort:
    return HttpxWbCatalogGateway(
        dest=settings.WB_DEST,
        timeout=settings.WB_REQUEST_TIMEOUT,
        proxies=settings.WB_PROXIES or None,
    )


def build_collect_products() -> CollectProducts:
    """Assemble the CollectProducts use case (used by the CLI and, later, Celery)."""
    return CollectProducts(
        gateway=build_wb_gateway(),
        repository=get_product_repository(),
        event_bus=get_catalog_event_bus(),
        clock=get_catalog_clock(),
        default_max_pages=settings.WB_MAX_PAGES,
    )


def build_list_products() -> ListProducts:
    """Assemble the ListProducts use case (used by the HTTP list view)."""
    return ListProducts(repository=get_product_repository())


def build_parse_job_repository() -> ParseJobRepositoryPort:
    return DjangoParseJobRepository()


def build_task_queue() -> TaskQueuePort:
    # Imported lazily to avoid importing the Celery app at module import time.
    from config.celery import app as celery_app

    return CeleryTaskQueue(celery_app)


def build_enqueue_collection() -> EnqueueCollection:
    """Assemble the EnqueueCollection use case (used by POST /api/parse/)."""
    return EnqueueCollection(repository=build_parse_job_repository(), queue=build_task_queue())

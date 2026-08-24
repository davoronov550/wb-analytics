"""Composition-root wiring tests — no DB needed (repo is only instantiated)."""

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.application.use_cases.collect_products import CollectProducts
from catalog.composition import container
from shared.composition import get_event_bus


def test_provides_product_repository():
    assert isinstance(container.get_product_repository(), DjangoProductRepository)


def test_builds_collect_products_use_case():
    # Construction only — no network/DB is touched until execute() runs.
    assert isinstance(container.build_collect_products(), CollectProducts)


def test_event_bus_is_the_shared_singleton():
    assert container.get_catalog_event_bus() is get_event_bus()


def test_clock_is_provided():
    assert container.get_catalog_clock().now() is not None

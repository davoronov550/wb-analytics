"""Composition-root wiring tests (T021) — no DB needed (repo is only instantiated)."""

from catalog.adapters.outbound.persistence.repository import DjangoProductRepository
from catalog.composition import container
from shared.composition import get_event_bus


def test_provides_product_repository():
    assert isinstance(container.get_product_repository(), DjangoProductRepository)


def test_event_bus_is_the_shared_singleton():
    assert container.get_catalog_event_bus() is get_event_bus()


def test_clock_is_provided():
    assert container.get_catalog_clock().now() is not None

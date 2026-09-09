"""Use-case tests for CollectProducts — fake ports, no DB, no network.

 Verifies: RawProduct→domain mapping, per-item skip of records
that can't form a valid Product, idempotent counts from the repository, the
ProductsCollected event, and max_pages resolution (command overrides default).
"""

from datetime import UTC, datetime
from typing import Any

from catalog.application.dto import CollectInput, RawProduct, UpsertResult
from catalog.application.events import DomainEvent, ProductsCollected
from catalog.application.ports.shared import EventHandler
from catalog.application.use_cases.collect_products import CollectProducts
from catalog.domain.product import Product

TS = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


class FakeGateway:
    def __init__(self, raws: list[RawProduct]) -> None:
        self._raws = raws
        self.calls: list[tuple[str, int]] = []

    def fetch(self, query: str, max_pages: int) -> list[RawProduct]:
        self.calls.append((query, max_pages))
        return list(self._raws)


class FakeRepository:
    """Simulates idempotent upsert by wb_id."""

    def __init__(self) -> None:
        self.store: dict[int, Product] = {}

    def upsert_many(self, products: list[Product], source_query: str) -> UpsertResult:
        created = updated = 0
        for product in products:
            if product.wb_id in self.store:
                updated += 1
            else:
                created += 1
            self.store[product.wb_id] = product
        return UpsertResult(created=created, updated=updated)

    def list(self, *args: object, **kwargs: object) -> Any:  # pragma: no cover - not used here
        raise NotImplementedError


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None:  # pragma: no cover - not used here
        pass

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


class FakeClock:
    def now(self) -> datetime:
        return TS


def _valid_raws() -> list[RawProduct]:
    return [
        RawProduct(
            1, "A", price_kopecks=599900, sale_price_kopecks=299900, rating=4.7, reviews=1234
        ),
        RawProduct(
            2, "B", price_kopecks=1000000, sale_price_kopecks=850000, rating=4.1, reviews=50
        ),
    ]


def _make(
    gateway: FakeGateway,
    repository: FakeRepository,
    bus: FakeEventBus,
    default_max_pages: int = 10,
) -> CollectProducts:
    return CollectProducts(
        gateway=gateway,
        repository=repository,
        event_bus=bus,
        clock=FakeClock(),
        default_max_pages=default_max_pages,
    )


def test_maps_upserts_and_publishes_event() -> None:
    raws = [
        *_valid_raws(),
        # Missing price → cannot build a domain Product → skipped.
        RawProduct(3, "C", price_kopecks=None, sale_price_kopecks=None, rating=None, reviews=None),
    ]
    gateway, repo, bus = FakeGateway(raws), FakeRepository(), FakeEventBus()

    result = _make(gateway, repo, bus).execute(CollectInput(query="наушники", max_pages=3))

    assert (result.created, result.updated, result.collected_count) == (2, 0, 2)
    assert result.query == "наушники"
    assert result.finished_at == TS
    assert set(repo.store) == {1, 2}  # C skipped

    assert gateway.calls == [("наушники", 3)]

    assert len(bus.published) == 1
    event = bus.published[0]
    assert isinstance(event, ProductsCollected)
    assert event.query == "наушники"
    assert set(event.wb_ids) == {1, 2}
    assert event.collected_count == 2
    assert event.occurred_at == TS


def test_reparse_is_idempotent_no_duplicates() -> None:
    gateway, repo, bus = FakeGateway(_valid_raws()), FakeRepository(), FakeEventBus()
    use_case = _make(gateway, repo, bus)

    first = use_case.execute(CollectInput(query="наушники"))
    second = use_case.execute(CollectInput(query="наушники"))

    assert (first.created, first.updated) == (2, 0)
    assert (second.created, second.updated) == (0, 2)
    assert set(repo.store) == {1, 2}


def test_default_max_pages_used_when_command_omits_it() -> None:
    gateway, repo, bus = FakeGateway(_valid_raws()), FakeRepository(), FakeEventBus()

    _make(gateway, repo, bus, default_max_pages=7).execute(CollectInput(query="q"))

    assert gateway.calls == [("q", 7)]

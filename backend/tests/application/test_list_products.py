"""Use-case tests for ListProducts (T030) — fake repository, no DB.

RED before T036. Verifies domain Product → ProductView mapping (incl. discount
fields) and pass-through of filter/ordering/pagination to the repository.
"""

from decimal import Decimal

from catalog.application.use_cases.list_products import ListProducts

from catalog.application.dto import Ordering, Page, ProductFilter, ProductView
from catalog.domain.product import Product
from shared.domain.value_objects import Money, Rating, ReviewsCount


def _product(wb_id=1, price="100.00", sale="60.00", rating="4.5", reviews=100, name="A", query="q"):
    return Product.rehydrate(
        wb_id=wb_id,
        name=name,
        price=Money(Decimal(price)),
        sale_price=Money(Decimal(sale)),
        rating=Rating(Decimal(rating)),
        reviews_count=ReviewsCount(reviews),
        source_query=query,
    )


class FakeRepository:
    def __init__(self, page):
        self._page = page
        self.calls = []

    def upsert_many(self, *args, **kwargs):  # pragma: no cover - not used here
        raise NotImplementedError

    def list(self, filter, ordering, page, page_size):
        self.calls.append((filter, ordering, page, page_size))
        return self._page


def test_maps_domain_products_to_views_with_discount_fields():
    repo = FakeRepository(Page(items=[_product()], count=1, page=1, page_size=1000))

    result = ListProducts(repository=repo).execute(
        ProductFilter(min_rating=Decimal("4")), Ordering(field="price"), 1, 1000
    )

    assert isinstance(result, Page)
    assert result.count == 1
    view = result.items[0]
    assert isinstance(view, ProductView)
    assert view.wb_id == 1
    assert view.price == Decimal("100.00")
    assert view.sale_price == Decimal("60.00")
    assert view.discount_abs == Decimal("40.00")
    assert view.discount_pct == Decimal("40.00")
    assert view.rating == Decimal("4.5")
    assert view.reviews_count == 100
    assert view.query == "q"


def test_passes_filter_ordering_pagination_to_repository():
    repo = FakeRepository(Page(items=[], count=0, page=2, page_size=50))
    product_filter = ProductFilter(min_price=Decimal("5000"))
    ordering = Ordering(field="reviews_count", descending=True)

    ListProducts(repository=repo).execute(product_filter, ordering, 2, 50)

    assert repo.calls == [(product_filter, ordering, 2, 50)]


def test_preserves_page_metadata():
    repo = FakeRepository(Page(items=[], count=123, page=3, page_size=20))

    result = ListProducts(repository=repo).execute(ProductFilter(), Ordering(), 3, 20)

    assert (result.count, result.page, result.page_size) == (123, 3, 20)

"""`GET /v1/products` отдаёт те же байты, что Django (T130).

DoD задачи — побайтовое совпадение, и проверялось оно сравнением с живым
Django на одинаковых данных: тринадцать запросов, ноль расхождений. Здесь это
зафиксировано в форме, которую можно перепроверить без Django — эталонная
строка снята с его ответа и вставлена дословно.

Почему именно байты, а не «структурно эквивалентный JSON». На канареечном
выводе (T143) один и тот же запрос уходит то в одну реализацию, то в другую.
Различие вида `"4.0"` против `"4.00"` или `2600.0` против `"2600.00"` не
поймает ни один структурный сравниватель, а клиент увидит его как мерцание
данных — и, если где-то делается сравнение строк, как ложное изменение.

База здесь не нужна: проверяется сериализация, а не выборка. Репозиторий
подменён, и подмена типизирована по порту — расхождение с ним поймает mypy.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalog.adapters.inbound.http.routes import _session, router
from catalog.application.dto import Ordering, Page, ProductFilter
from catalog.domain.product import Product
from catalog.domain.value_objects import Money, Rating, ReviewsCount

#: Ответ Django на `GET /api/products/?page_size=1` для товара ниже. Снят с
#: работающего сервера и вставлен дословно, включая отсутствие пробелов после
#: разделителей и неэкранированную кириллицу.
DJANGO_RESPONSE = (
    b'{"count":60,"next":null,"previous":null,"results":['
    b'{"wb_id":1005,"name":"\xd0\xa2\xd0\xbe\xd0\xb2\xd0\xb0\xd1\x80 1005",'
    b'"price":"1100.00","sale_price":"1000.00","discount_abs":"100.00",'
    b'"discount_pct":"9.09","rating":"2.0","reviews_count":50,'
    b'"query":"\xd0\xbd\xd0\xb0\xd1\x83\xd1\x88\xd0\xbd\xd0\xb8\xd0\xba\xd0\xb8",'
    b'"updated_at":null}]}'
)

#: Репозиторий отдаёт доменные сущности, а в `ProductView` их превращает
#: сценарий — поэтому подделка возвращает `Product`, а не готовое представление.
#: Скидка при этих числах считается сама: 1100 − 1000 = 100, и 100/1100 = 9.09 %.
PRODUCT = Product.rehydrate(
    wb_id=1005,
    name="Товар 1005",
    price=Money(Decimal("1100.00")),
    sale_price=Money(Decimal("1000.00")),
    rating=Rating(Decimal("2.0")),
    reviews_count=ReviewsCount(50),
    source_query="наушники",
)


class FakeRepository:
    """Подделка порта: отдаёт заранее известную страницу."""

    def __init__(self, page: Page[Any]) -> None:
        self._page = page
        self.calls: list[tuple[ProductFilter, Ordering, int, int]] = []

    async def upsert_many(self, *args: object, **kwargs: object) -> Any:
        raise NotImplementedError  # pragma: no cover - не используется здесь

    async def list(
        self, filter: ProductFilter, ordering: Ordering, page: int, page_size: int
    ) -> Page[Any]:
        self.calls.append((filter, ordering, page, page_size))
        return self._page


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository(Page(items=[PRODUCT], count=60, page=1, page_size=1))


@pytest.fixture
def client(repository: FakeRepository, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Приложение только с этим роутером: фабрика сервиса требует настроенного
    окружения, а проверяется здесь один обработчик."""
    import catalog.adapters.inbound.http.routes as routes

    monkeypatch.setattr(routes, "SqlAlchemyProductRepository", lambda _session: repository)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_session] = lambda: None
    return TestClient(app)


class TestBytesMatchDjango:
    def test_the_response_is_byte_identical(self, client: TestClient) -> None:
        response = client.get("/v1/products?page_size=1")

        assert response.content == DJANGO_RESPONSE

    def test_decimals_are_strings_not_numbers(self, client: TestClient) -> None:
        """`COERCE_DECIMAL_TO_STRING` у DRF — умолчание. Число потеряло бы
        хвостовые нули, а на больших значениях и точность."""
        body = client.get("/v1/products?page_size=1").json()

        assert isinstance(body["results"][0]["price"], str)
        assert isinstance(body["results"][0]["rating"], str)

    def test_rating_keeps_one_decimal_place(self, client: TestClient) -> None:
        """`"2.0"`, а не `"2"` и не `"2.00"`: у DRF здесь `decimal_places=1`."""
        body = client.get("/v1/products?page_size=1").json()

        assert body["results"][0]["rating"] == "2.0"

    def test_integers_stay_integers(self, client: TestClient) -> None:
        """Не всё подряд в строки: `wb_id` и `reviews_count` у Django числа."""
        body = client.get("/v1/products?page_size=1").json()

        assert isinstance(body["results"][0]["wb_id"], int)
        assert isinstance(body["results"][0]["reviews_count"], int)

    def test_cyrillic_is_not_escaped(self, client: TestClient) -> None:
        """Рендерер DRF отдаёт UTF-8, а не `\\uXXXX`."""
        assert "Товар".encode() in client.get("/v1/products?page_size=1").content


class TestQueryParameters:
    def test_filters_reach_the_use_case(
        self, client: TestClient, repository: FakeRepository
    ) -> None:
        client.get("/v1/products?min_price=1500&max_rating=4&min_reviews=10")
        (product_filter, _, _, _) = repository.calls[0]

        assert product_filter.min_price == Decimal("1500")
        assert product_filter.max_rating == Decimal("4")
        assert product_filter.min_reviews == 10

    def test_single_level_sort_still_works(
        self, client: TestClient, repository: FakeRepository
    ) -> None:
        """`?ordering=` — формат, которым пользуется текущий фронтенд."""
        client.get("/v1/products?ordering=-rating")
        (_, ordering, _, _) = repository.calls[0]

        assert [(k.field, k.descending) for k in ordering.keys] == [("rating", True)]

    def test_multi_level_sort_arrives_whole(
        self, client: TestClient, repository: FakeRepository
    ) -> None:
        """То, ради чего делался T110: все уровни доходят до сервера, а не
        только первый."""
        client.get("/v1/products?sort=sale_price,-rating")
        (_, ordering, _, _) = repository.calls[0]

        assert [(k.field, k.descending) for k in ordering.keys] == [
            ("sale_price", False),
            ("rating", True),
        ]

    def test_page_size_above_the_cap_is_clamped_not_refused(
        self, client: TestClient, repository: FakeRepository
    ) -> None:
        """Так делает Django. Отказ вместо обрезания сломал бы клиента,
        который просит больше."""
        client.get("/v1/products?page_size=99999")
        (_, _, _, page_size) = repository.calls[0]

        assert page_size == 1000

    def test_defaults_match_django(self, client: TestClient, repository: FakeRepository) -> None:
        client.get("/v1/products")
        (product_filter, ordering, page, page_size) = repository.calls[0]

        assert (page, page_size) == (1, 1000)
        assert product_filter == ProductFilter()
        assert [(k.field, k.descending) for k in ordering.keys] == [("reviews_count", True)]

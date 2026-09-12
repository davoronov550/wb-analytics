"""HTTP-маршруты каталога (T130).

Адаптер тонкий по назначению: разобрать запрос, вызвать сценарий, отдать JSON.
Ни одного решения о предметной области здесь нет — они в `application/`, и
именно поэтому адаптер можно было написать заново, не трогая перенесённый слой.

Префикс `/v1`, а не `/api`: Django отвечает на оба (T065), поэтому переключение
на этот сервис в T140 — правка маршрута в Traefik, а не правка клиента.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.adapters.inbound.http.request_filters import (
    parse_ordering,
    parse_pagination,
    parse_product_filter,
)
from catalog.adapters.inbound.http.schemas import ProductPageSchema, ProductViewSchema
from catalog.adapters.outbound.persistence.repository import SqlAlchemyProductRepository
from catalog.application.use_cases.list_products import ListProducts

__all__ = ["router"]

router = APIRouter(prefix="/v1", tags=["catalog"])


async def _session(request: Request) -> AsyncIterator[AsyncSession]:
    """Сессия на запрос из фабрики, собранной в композиционном корне.

    Одна сессия на запрос, а не на приложение: сессия SQLAlchemy не потокобезопасна
    и держит соединение, а за PgBouncer в режиме транзакций удержание соединения
    между запросами обесценивает мультиплексирование, ради которого пулер и стоит.
    """
    factory = request.app.state.container.session_factory
    async with factory() as session:
        yield session


@router.get(
    "/products",
    response_model=None,
    summary="Список товаров с фильтрами, сортировкой и пагинацией",
)
async def list_products(
    request: Request,
    session: Annotated[AsyncSession, Depends(_session)],
) -> ProductPageSchema:
    """Страница товаров — тот же ответ, что отдаёт Django на `/api/products/`.

    Параметры читаются из `request.query_params`, а не объявляются аргументами:
    правила у них перекрёстные, и разбор живёт одним куском в
    `request_filters`, общим с проверкой на совпадение с Django.
    """
    params = request.query_params
    page, page_size = parse_pagination(params)

    result = await ListProducts(repository=SqlAlchemyProductRepository(session)).execute(
        parse_product_filter(params),
        parse_ordering(params),
        page,
        page_size,
    )

    return ProductPageSchema(
        count=result.count,
        results=tuple(
            ProductViewSchema(
                wb_id=view.wb_id,
                name=view.name,
                price=view.price,
                sale_price=view.sale_price,
                discount_abs=view.discount_abs,
                discount_pct=view.discount_pct,
                rating=view.rating,
                reviews_count=view.reviews_count,
                query=view.query,
                updated_at=view.updated_at,
            )
            for view in result.items
        ),
    )

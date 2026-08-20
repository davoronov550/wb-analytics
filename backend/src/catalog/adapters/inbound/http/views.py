"""Catalog HTTP views (inbound adapter) — thin: parse request → use case → JSON."""

from __future__ import annotations

from collections.abc import Mapping

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.adapters.inbound.http.request_filters import parse_ordering, parse_product_filter
from catalog.adapters.inbound.http.serializers import ProductViewSerializer
from catalog.application.errors import InvalidFilter
from catalog.composition import container

_MAX_PAGE_SIZE = 1000


def _positive_int(params: Mapping, key: str, default: int, maximum: int | None = None) -> int:
    raw = params.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidFilter(f"{key} must be an integer") from exc
    if value < 1:
        raise InvalidFilter(f"{key} must be >= 1")
    if maximum is not None:
        value = min(value, maximum)
    return value


class ProductListView(APIView):
    def get(self, request: Request) -> Response:
        params = request.query_params
        product_filter = parse_product_filter(params)
        ordering = parse_ordering(params)
        page = _positive_int(params, "page", default=1)
        page_size = _positive_int(
            params, "page_size", default=_MAX_PAGE_SIZE, maximum=_MAX_PAGE_SIZE
        )

        result = container.build_list_products().execute(product_filter, ordering, page, page_size)
        results = ProductViewSerializer(result.items, many=True).data
        return Response({"count": result.count, "next": None, "previous": None, "results": results})

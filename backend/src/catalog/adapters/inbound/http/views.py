"""Catalog HTTP views (inbound adapter) — thin: parse request → use case → JSON."""

from __future__ import annotations

from collections.abc import Mapping

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from catalog.adapters.inbound.http.request_filters import parse_ordering, parse_product_filter
from catalog.adapters.inbound.http.schema_params import PRODUCT_LIST_PARAMETERS
from catalog.adapters.inbound.http.serializers import (
    ErrorSerializer,
    ParseEnqueuedSerializer,
    ParseJobSerializer,
    ParseRequestSerializer,
    ProductPageSerializer,
    ProductViewSerializer,
)
from catalog.application.errors import InvalidFilter
from catalog.composition import container

_MAX_PAGE_SIZE = 1000
_MAX_PARSE_PAGES = 20
# Width of ParseJobModel.query. Checked here because PostgreSQL raises
# DataError at INSERT otherwise, after the request was already accepted as
# valid — the client gets a 500 for input the API should have refused.
# `test_malformed_input` ties this to the column so widening one without the
# other fails a test instead of a request.
_MAX_PARSE_QUERY = 200


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
    @extend_schema(
        operation_id="products_list",
        summary="List products",
        parameters=PRODUCT_LIST_PARAMETERS,
        responses={200: ProductPageSerializer, 400: ErrorSerializer},
    )
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


class ParseView(APIView):
    """POST /api/parse/ — enqueue an async collection run, returns 202."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "parse"

    @extend_schema(
        operation_id="collections_create",
        summary="Enqueue a collection run",
        # JSON only. `COMPONENT_SPLIT_REQUEST` otherwise advertises the two
        # form encodings as well, and neither can carry this body: a nested
        # object arrives as the string "{'kind': ...}" and a null as the
        # string "None". The API answers 400, correctly — the schema was
        # promising a media type that cannot work.
        request={"application/json": ParseRequestSerializer},
        responses={
            202: ParseEnqueuedSerializer,
            400: ErrorSerializer,
            429: ErrorSerializer,
            502: ErrorSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, Mapping) else {}
        query = data.get("query")
        if not isinstance(query, str) or not query.strip():
            raise InvalidFilter("query is required")
        if len(query.strip()) > _MAX_PARSE_QUERY:
            raise InvalidFilter(f"query must be at most {_MAX_PARSE_QUERY} characters")
        max_pages = self._parse_max_pages(data.get("max_pages"))

        job = container.build_enqueue_collection().execute(query.strip(), max_pages)
        return Response(
            {"task_id": job.task_id, "query": job.query, "status": job.status},
            status=202,
        )

    @staticmethod
    def _parse_max_pages(raw: object) -> int | None:
        if raw is None or raw == "":
            return None
        try:
            value = int(raw)  # type: ignore[arg-type]
        except (ValueError, TypeError) as exc:
            raise InvalidFilter("max_pages must be an integer") from exc
        if not (1 <= value <= _MAX_PARSE_PAGES):
            raise InvalidFilter(f"max_pages must be within [1, {_MAX_PARSE_PAGES}]")
        return value


class TaskStatusView(APIView):
    """GET /api/tasks/{task_id}/ — async collection status."""

    @extend_schema(
        operation_id="collections_retrieve",
        summary="Collection run status",
        responses={200: ParseJobSerializer, 404: ErrorSerializer},
    )
    def get(self, request: Request, task_id: str) -> Response:
        job = container.build_parse_job_repository().get(task_id)
        if job is None:
            return Response({"detail": "Task not found."}, status=404)
        return Response(ParseJobSerializer(job).data)

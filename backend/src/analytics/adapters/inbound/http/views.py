"""Analytics HTTP views (inbound adapter) — price history."""

from __future__ import annotations

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from analytics.adapters.inbound.http.serializers import (
    PriceHistorySerializer,
    QueryComparisonSerializer,
    SnapshotSerializer,
    StatsSerializer,
)
from analytics.adapters.outbound.export.writers import build_xlsx, iter_csv
from analytics.composition import container
from catalog.adapters.inbound.http.request_filters import (
    BIGINT_MAX,
    parse_ordering,
    parse_product_filter,
)
from catalog.adapters.inbound.http.schema_params import ANALYTICS_PARAMETERS, ORDERING_PARAMETERS
from catalog.adapters.inbound.http.serializers import ErrorSerializer
from catalog.application.errors import InvalidFilter

_XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class HistoryView(APIView):
    """GET /api/products/{wb_id}/history/ — a product's price time-series."""

    @extend_schema(
        operation_id="products_price_history",
        summary="Price history of one product",
        # 404 is not "no such product" — an unknown id answers 200 with an empty
        # series. It is the routing miss: `<int:wb_id>` does not match a
        # non-numeric id, and that path now returns an envelope.
        responses={200: PriceHistorySerializer, 404: ErrorSerializer},
    )
    def get(self, request: Request, wb_id: int) -> Response:
        if not (-BIGINT_MAX - 1 <= wb_id <= BIGINT_MAX):
            raise InvalidFilter("wb_id is out of range")
        snapshots = container.build_list_history().execute(wb_id)
        return Response({"wb_id": wb_id, "points": SnapshotSerializer(snapshots, many=True).data})


class StatsView(APIView):
    """GET /api/stats/ — aggregates for a filtered set; repeated `query=` compares.

    One query → a single Stats object. Two or more `query=` params → comparison
    : `{"items": [{"query", "stats"}, ..]}`, one per query, all sharing the
    other filters.
    """

    @extend_schema(
        operation_id="stats_retrieve",
        summary="Aggregates for a filtered set, or a comparison of queries",
        description=(
            "One `query` returns a Stats object. Two or more return "
            "`{items: [{query, stats}]}` — the same path answers with a "
            "different shape, which is why both are declared."
        ),
        parameters=[
            *ANALYTICS_PARAMETERS,
            OpenApiParameter(
                name="query",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                many=True,
                description="Repeat to compare queries side by side.",
            ),
        ],
        responses={
            200: OpenApiResponse(
                # Two shapes behind one status code, emitted as `oneOf`. There
                # is no discriminator field to key on — the shapes differ
                # structurally (`items` present or not) — so the discriminator
                # is disabled explicitly. drf-spectacular warns that this can
                # break client generation, which is true and still the better
                # trade: naming only the first shape does not break generation,
                # it makes the generated client parse a comparison response as
                # a Stats object and read every aggregate as missing.
                response=PolymorphicProxySerializer(
                    component_name="StatsOrComparison",
                    serializers=[StatsSerializer, QueryComparisonSerializer],
                    resource_type_field_name=None,
                    many=False,
                ),
                description="Single query: Stats. Repeated query: {items: [{query, stats}]}.",
            ),
            400: ErrorSerializer,
        },
    )
    def get(self, request: Request) -> Response:
        product_filter = parse_product_filter(request.query_params)  # InvalidFilter → 400
        queries = request.query_params.getlist("query")
        if len(queries) > 1:
            items = container.build_compare_queries().execute(queries, product_filter)
            return Response(
                {
                    "items": [
                        {"query": item.query, "stats": StatsSerializer(item.stats).data}
                        for item in items
                    ]
                }
            )
        stats = container.build_compute_stats().execute(product_filter)
        return Response(StatsSerializer(stats).data)


class ExportView(APIView):
    """GET /api/export/?format=csv|xlsx — the filtered product set as a file.

    Authenticated-only: this dumps the whole filtered catalogue in one request, so
    it is an internal tool rather than part of the public catalogue read surface.
    Throttled for the same reason.

    ``format`` stays a plain query parameter because DRF's renderer-suffix lookup
    is disabled project-wide (``URL_FORMAT_OVERRIDE = None``).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "export"

    @extend_schema(
        operation_id="export_download",
        summary="Download the filtered set as a file",
        parameters=[
            *ANALYTICS_PARAMETERS,
            *ORDERING_PARAMETERS,
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                enum=["csv", "xlsx"],
                description="Defaults to csv.",
            ),
        ],
        responses={
            # A file, not JSON. Declared as binary with both content types so a
            # generated client reads bytes instead of trying to parse them.
            (200, "text/csv"): OpenApiTypes.BINARY,
            (200, _XLSX_TYPE): OpenApiTypes.BINARY,
            400: ErrorSerializer,
            401: ErrorSerializer,
            429: ErrorSerializer,
        },
    )
    def get(self, request: Request) -> HttpResponse:
        try:
            product_filter = parse_product_filter(request.query_params)
            ordering = parse_ordering(request.query_params)
        except InvalidFilter as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
        rows = container.build_export_products().execute(product_filter, ordering)

        if request.query_params.get("format") == "xlsx":
            response = HttpResponse(build_xlsx(rows), content_type=_XLSX_TYPE)
            response["Content-Disposition"] = 'attachment; filename="products.xlsx"'
            return response

        response = StreamingHttpResponse(iter_csv(rows), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="products.csv"'
        return response

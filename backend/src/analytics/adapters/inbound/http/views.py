"""Analytics HTTP views (inbound adapter) — price history (FE-04)."""

from __future__ import annotations

from django.http import HttpResponse, StreamingHttpResponse
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.adapters.inbound.http.serializers import SnapshotSerializer, StatsSerializer
from analytics.adapters.outbound.export.writers import build_xlsx, iter_csv
from analytics.composition import container
from catalog.adapters.inbound.http.request_filters import parse_ordering, parse_product_filter

_XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class HistoryView(APIView):
    """GET /api/products/{wb_id}/history/ — a product's price time-series."""

    def get(self, request: Request, wb_id: int) -> Response:
        snapshots = container.build_list_history().execute(wb_id)
        return Response({"wb_id": wb_id, "points": SnapshotSerializer(snapshots, many=True).data})


class StatsView(APIView):
    """GET /api/stats/ — aggregates for a filtered set; repeated `query=` compares.

    One query → a single Stats object. Two or more `query=` params → comparison
    (FE-06): `{"items": [{"query", "stats"}, ...]}`, one per query, all sharing the
    other filters.
    """

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
    """GET /api/export/?format=csv|xlsx — the filtered product set as a file (FE-08)."""

    def get(self, request: Request) -> HttpResponse:
        product_filter = parse_product_filter(request.query_params)  # InvalidFilter → 400
        ordering = parse_ordering(request.query_params)
        rows = container.build_export_products().execute(product_filter, ordering)

        if request.query_params.get("format") == "xlsx":
            response = HttpResponse(build_xlsx(rows), content_type=_XLSX_TYPE)
            response["Content-Disposition"] = 'attachment; filename="products.xlsx"'
            return response

        response = StreamingHttpResponse(iter_csv(rows), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="products.csv"'
        return response

"""Analytics HTTP views (inbound adapter) — price history (FE-04)."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.adapters.inbound.http.serializers import SnapshotSerializer, StatsSerializer
from analytics.composition import container
from catalog.adapters.inbound.http.request_filters import parse_product_filter


class HistoryView(APIView):
    """GET /api/products/{wb_id}/history/ — a product's price time-series."""

    def get(self, request: Request, wb_id: int) -> Response:
        snapshots = container.build_list_history().execute(wb_id)
        return Response({"wb_id": wb_id, "points": SnapshotSerializer(snapshots, many=True).data})


class StatsView(APIView):
    """GET /api/stats/ — aggregates for a filtered set (same filters as products)."""

    def get(self, request: Request) -> Response:
        product_filter = parse_product_filter(request.query_params)  # InvalidFilter → 400
        stats = container.build_compute_stats().execute(product_filter)
        return Response(StatsSerializer(stats).data)

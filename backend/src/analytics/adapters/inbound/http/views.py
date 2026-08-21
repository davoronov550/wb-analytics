"""Analytics HTTP views (inbound adapter) — price history (FE-04)."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.adapters.inbound.http.serializers import SnapshotSerializer
from analytics.composition import container


class HistoryView(APIView):
    """GET /api/products/{wb_id}/history/ — a product's price time-series."""

    def get(self, request: Request, wb_id: int) -> Response:
        snapshots = container.build_list_history().execute(wb_id)
        return Response({"wb_id": wb_id, "points": SnapshotSerializer(snapshots, many=True).data})

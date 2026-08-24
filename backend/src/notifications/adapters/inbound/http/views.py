"""Notifications HTTP views (inbound adapter) — owner-scoped alert CRUD."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.adapters.inbound.http.serializers import AlertRuleSerializer
from notifications.composition import container


class AlertListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        rules = container.build_manage_alerts().list(request.user.id)
        return Response(AlertRuleSerializer(rules, many=True).data)

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, Mapping) else {}
        target = data.get("target") or {}
        condition = data.get("condition") or {}
        try:
            value = Decimal(str(condition.get("value")))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError({"detail": "condition.value must be a number"}) from exc
        try:
            rule = container.build_manage_alerts().create(
                owner_id=request.user.id,
                kind=str(condition.get("kind")),
                value=value,
                channel=str(data.get("channel")),
                target_wb_id=target.get("wb_id"),
                target_query=target.get("query"),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(AlertRuleSerializer(rule).data, status=201)


class AlertDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, rule_id: int) -> Response:
        deleted = container.build_manage_alerts().delete(request.user.id, rule_id)
        return Response(status=204 if deleted else 404)

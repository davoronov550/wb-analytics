"""Scheduling HTTP views (inbound adapter) — CRUD + enable/disable (FE-01)."""

from __future__ import annotations

from collections.abc import Mapping

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from scheduling.adapters.inbound.http.serializers import ScheduleSerializer
from scheduling.composition import container


class ScheduleListView(APIView):
    def get(self, request: Request) -> Response:
        schedules = container.build_manage_schedules().list()
        return Response(ScheduleSerializer(schedules, many=True).data)

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, Mapping) else {}
        query = data.get("query")
        spec = data.get("spec")
        if not query or not spec:
            raise ValidationError({"detail": "query and spec are required"})
        try:
            schedule = container.build_manage_schedules().create(
                query=str(query), spec=str(spec), active=bool(data.get("active", True))
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(ScheduleSerializer(schedule).data, status=201)


class ScheduleDetailView(APIView):
    def patch(self, request: Request, schedule_id: int) -> Response:
        manager = container.build_manage_schedules()
        if container.build_schedule_repository().get(schedule_id) is None:
            return Response({"detail": "Schedule not found."}, status=404)
        active = request.data.get("active")
        if not isinstance(active, bool):
            raise ValidationError({"detail": "active (boolean) is required"})
        schedule = manager.set_active(schedule_id, active)
        return Response(ScheduleSerializer(schedule).data)

    def delete(self, request: Request, schedule_id: int) -> Response:
        if container.build_schedule_repository().get(schedule_id) is None:
            return Response({"detail": "Schedule not found."}, status=404)
        container.build_manage_schedules().delete(schedule_id)
        return Response(status=204)

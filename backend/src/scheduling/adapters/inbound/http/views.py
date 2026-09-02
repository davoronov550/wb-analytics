"""Scheduling HTTP views (inbound adapter) — CRUD + enable/disable.

Owner-scoped: schedules require authentication and each user only sees and
mutates their own (foreign ids return 404, never leaking existence).
"""

from __future__ import annotations

from collections.abc import Mapping

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.adapters.inbound.http.serializers import ErrorSerializer
from scheduling.adapters.inbound.http.serializers import ScheduleSerializer
from scheduling.composition import container


def _owned_or_none(schedule_id: int, owner_id: int):
    schedule = container.build_schedule_repository().get(schedule_id)
    if schedule is None or schedule.owner_id != owner_id:
        return None
    return schedule


class ScheduleListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="schedules_list",
        summary="List the caller's schedules",
        responses={200: ScheduleSerializer(many=True), 401: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        schedules = container.build_manage_schedules().list(owner_id=request.user.id)
        return Response(ScheduleSerializer(schedules, many=True).data)

    @extend_schema(
        operation_id="schedules_create",
        summary="Create a schedule",
        request=ScheduleSerializer,
        responses={201: ScheduleSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, Mapping) else {}
        query = data.get("query")
        spec = data.get("spec")
        if not query or not spec:
            raise ValidationError({"detail": "query and spec are required"})
        try:
            schedule = container.build_manage_schedules().create(
                query=str(query),
                spec=str(spec),
                active=bool(data.get("active", True)),
                owner_id=request.user.id,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(ScheduleSerializer(schedule).data, status=201)


class ScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="schedules_set_active",
        summary="Enable or disable a schedule",
        request=ScheduleSerializer,
        # 404 rather than 403 for someone else's id: 403 would confirm it exists.
        responses={
            200: ScheduleSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
        },
    )
    def patch(self, request: Request, schedule_id: int) -> Response:
        if _owned_or_none(schedule_id, request.user.id) is None:
            return Response({"detail": "Schedule not found."}, status=404)
        active = request.data.get("active")
        if not isinstance(active, bool):
            raise ValidationError({"detail": "active (boolean) is required"})
        schedule = container.build_manage_schedules().set_active(schedule_id, active)
        return Response(ScheduleSerializer(schedule).data)

    @extend_schema(
        operation_id="schedules_destroy",
        summary="Delete a schedule",
        responses={204: None, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def delete(self, request: Request, schedule_id: int) -> Response:
        if _owned_or_none(schedule_id, request.user.id) is None:
            return Response({"detail": "Schedule not found."}, status=404)
        container.build_manage_schedules().delete(schedule_id)
        return Response(status=204)

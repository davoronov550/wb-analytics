"""Scheduling HTTP serializers (read model for schedules)."""

from __future__ import annotations

from rest_framework import serializers


class ScheduleSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    query = serializers.CharField()
    spec = serializers.CharField()
    interval_seconds = serializers.IntegerField(read_only=True)
    active = serializers.BooleanField(required=False, default=True)
    last_run_at = serializers.DateTimeField(read_only=True, allow_null=True)

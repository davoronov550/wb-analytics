"""Notifications HTTP serializers (alert read model)."""

from __future__ import annotations

from rest_framework import serializers


class AlertRuleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    channel = serializers.CharField()
    target_wb_id = serializers.IntegerField(allow_null=True)
    target_query = serializers.CharField(allow_null=True)
    active = serializers.BooleanField()

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


class AlertTargetSerializer(serializers.Serializer):
    """What the rule watches: one product, or every product of a query."""

    wb_id = serializers.IntegerField(required=False, allow_null=True)
    query = serializers.CharField(required=False, allow_null=True, max_length=200)


class AlertConditionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["abs_below", "pct_drop"])
    value = serializers.DecimalField(max_digits=10, decimal_places=2)


class CreateAlertSerializer(serializers.Serializer):
    """`POST /api/alerts/` body — nested, and validated by hand in the view."""

    target = AlertTargetSerializer()
    condition = AlertConditionSerializer()
    channel = serializers.ChoiceField(choices=["email", "telegram"])

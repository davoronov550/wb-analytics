"""Notifications HTTP serializers (alert read model)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(
    {
        # Two corrections to what DecimalField renders on its own.
        #
        # It emits `type: string` alone, but the view reads the value through
        # `Decimal(str(...))`, so a JSON number is accepted just as readily —
        # the schema was calling a working request invalid.
        #
        # It also emits `^-?\d{0,8}(?:\.\d{0,2})?$`, and every quantifier
        # there starts at zero: the empty string, "-" and "." all match. The
        # view answers those with 400, so the schema was calling a refused
        # request valid. `{1,8}` and `{1,2}` say what was meant.
        "anyOf": [
            {"type": "number"},
            {"type": "string", "pattern": r"^-?\d{1,8}(?:\.\d{1,2})?$"},
        ],
        "description": "A decimal, as a JSON number or a string.",
    }
)
class MoneyField(serializers.DecimalField):
    """A decimal the API accepts in either JSON form."""


class AlertRuleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    value = MoneyField(max_digits=10, decimal_places=2)
    channel = serializers.CharField()
    target_wb_id = serializers.IntegerField(allow_null=True)
    target_query = serializers.CharField(allow_null=True)
    active = serializers.BooleanField()


class AlertTargetSerializer(serializers.Serializer):
    """What the rule watches: one product, or every product of a query."""

    wb_id = serializers.IntegerField(required=False, allow_null=True)
    # `allow_blank`: вью принимает пустую строку и трактует её как
    # «цель не задана». Без этого схема объявляет minLength 1 и называет
    # некорректным запрос, который API выполняет.
    query = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=200
    )


class AlertConditionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["abs_below", "pct_drop"])
    value = MoneyField(max_digits=10, decimal_places=2)


class CreateAlertSerializer(serializers.Serializer):
    """`POST /api/alerts/` body — nested, and validated by hand in the view."""

    target = AlertTargetSerializer()
    condition = AlertConditionSerializer()
    channel = serializers.ChoiceField(choices=["email", "telegram"])

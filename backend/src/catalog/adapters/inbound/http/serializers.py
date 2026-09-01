"""DRF serializers for the catalog HTTP adapter.

Serializes the application ProductView read model (a dataclass) to JSON. Decimal
fields render as strings (e.g. "60.00").
"""

from __future__ import annotations

from rest_framework import serializers


class ProductViewSerializer(serializers.Serializer):
    wb_id = serializers.IntegerField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_abs = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_pct = serializers.DecimalField(max_digits=6, decimal_places=2)
    rating = serializers.DecimalField(max_digits=2, decimal_places=1)
    reviews_count = serializers.IntegerField()
    query = serializers.CharField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)


class ParseJobSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    query = serializers.CharField()
    status = serializers.CharField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    collected_count = serializers.IntegerField()
    error = serializers.CharField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)


# --- Response envelopes ---------------------------------------------------
#
# These describe shapes the views assemble by hand. Without them the schema
# generator falls back to an empty body, which produces a specification that
# validates nothing while looking complete.


class ErrorSerializer(serializers.Serializer):
    """The `{"detail": ...}` body every error path returns today.

    Named here rather than per context: the exception handler is shared, so
    one definition keeps the contract honest about that.
    """

    detail = serializers.CharField()


class ProductPageSerializer(serializers.Serializer):
    """`GET /api/products/` — DRF's page envelope, assembled manually."""

    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = ProductViewSerializer(many=True)


class ParseEnqueuedSerializer(serializers.Serializer):
    """`POST /api/parse/` — 202 with the accepted job, not the finished one."""

    task_id = serializers.CharField()
    query = serializers.CharField()
    status = serializers.CharField()


class ParseRequestSerializer(serializers.Serializer):
    """`POST /api/parse/` body. Validated by hand in the view, described here."""

    query = serializers.CharField(max_length=200)
    max_pages = serializers.IntegerField(
        required=False, min_value=1, max_value=20, help_text="Defaults to the server setting."
    )

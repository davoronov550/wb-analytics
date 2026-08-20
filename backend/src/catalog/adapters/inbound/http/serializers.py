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

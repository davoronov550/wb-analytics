"""Analytics HTTP serializers."""

from __future__ import annotations

from rest_framework import serializers


class SnapshotSerializer(serializers.Serializer):
    captured_at = serializers.DateTimeField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    rating = serializers.DecimalField(max_digits=2, decimal_places=1)

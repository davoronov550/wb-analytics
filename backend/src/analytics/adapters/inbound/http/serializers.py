"""Analytics HTTP serializers."""

from __future__ import annotations

from rest_framework import serializers


class SnapshotSerializer(serializers.Serializer):
    captured_at = serializers.DateTimeField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    rating = serializers.DecimalField(max_digits=2, decimal_places=1)


class TopProductSerializer(serializers.Serializer):
    wb_id = serializers.IntegerField()
    name = serializers.CharField()
    reviews_count = serializers.IntegerField()


class StatsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    avg_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    median_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    price_stddev = serializers.DecimalField(max_digits=10, decimal_places=2)
    avg_discount_abs = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_share = serializers.FloatField()
    top_by_reviews = TopProductSerializer(many=True)

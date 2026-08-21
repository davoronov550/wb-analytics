"""Accounts HTTP serializers."""

from __future__ import annotations

from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)


class SavedSearchSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=200)
    query = serializers.CharField(max_length=200)
    filters = serializers.JSONField(required=False, default=dict)

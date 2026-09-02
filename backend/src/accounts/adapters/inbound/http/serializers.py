"""Accounts HTTP serializers."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)


@extend_schema_field({"type": "object", "additionalProperties": True})
class FilterMapField(serializers.JSONField):
    """The saved filter set: an object, not arbitrary JSON.

    `JSONField` accepts any JSON value, so a list went in, was stored, and came
    back out of `GET /api/saved-searches/` as a list — where the response no
    longer matched the schema this very annotation declares. Validating here
    keeps the two ends agreeing instead of only the write end.
    """

    def to_internal_value(self, data: object) -> dict:
        value = super().to_internal_value(data)
        if not isinstance(value, dict):
            raise serializers.ValidationError("Expected an object of filters.")
        return value


class SavedSearchSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=200)
    query = serializers.CharField(max_length=200)
    # JSONField renders as the empty schema — "anything", null included — while
    # the field itself refuses null and the column holds a filter map. The
    # schema was inviting a request the API answers with 400.
    filters = FilterMapField(required=False, default=dict)


class AccountSerializer(serializers.Serializer):
    """The caller's own account, as `/auth/me/` and Google sign-in return it."""

    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_null=True)
    providers = serializers.ListField(child=serializers.CharField())


class RegisteredSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


class GoogleAuthRequestSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = AccountSerializer()


class LogoutRequestSerializer(serializers.Serializer):
    """`refresh` is optional: a client that has already lost it still gets 205,
    because there is nothing left to revoke.

    `allow_blank` for the same reason. Without it the schema advertises a
    minimum length the view does not enforce — an empty string is exactly the
    "already lost it" case the docstring describes, and it is answered with 205.
    """

    refresh = serializers.CharField(required=False, allow_blank=True)

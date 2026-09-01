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
    because there is nothing left to revoke."""

    refresh = serializers.CharField(required=False)

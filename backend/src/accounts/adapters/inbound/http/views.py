"""Accounts HTTP views (inbound adapter) — auth + saved searches (FE-09)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.adapters.inbound.http.serializers import RegisterSerializer, SavedSearchSerializer
from accounts.composition import container

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        if User.objects.filter(username=username).exists():
            raise ValidationError({"username": "already taken"})
        user = User.objects.create_user(
            username=username, password=serializer.validated_data["password"]
        )
        return Response({"id": user.id, "username": user.username}, status=201)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response({"id": request.user.id, "username": request.user.username})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        # Stateless JWT: the client discards the token; nothing to do server-side.
        return Response(status=status.HTTP_205_RESET_CONTENT)


class SavedSearchListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        items = container.build_manage_saved_searches().list(request.user.id)
        return Response(SavedSearchSerializer(items, many=True).data)

    def post(self, request: Request) -> Response:
        serializer = SavedSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = container.build_manage_saved_searches().create(
            owner_id=request.user.id,
            name=serializer.validated_data["name"],
            query=serializer.validated_data["query"],
            filters=serializer.validated_data.get("filters", {}),
        )
        return Response(SavedSearchSerializer(item).data, status=201)


class SavedSearchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, saved_id: int) -> Response:
        if not container.build_manage_saved_searches().delete(request.user.id, saved_id):
            return Response({"detail": "Not found."}, status=404)
        return Response(status=204)

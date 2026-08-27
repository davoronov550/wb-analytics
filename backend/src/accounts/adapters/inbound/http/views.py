"""Accounts HTTP views (inbound adapter) — auth + saved searches."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.adapters.inbound.http.serializers import RegisterSerializer, SavedSearchSerializer
from accounts.adapters.outbound.persistence.models import ExternalIdentityModel
from accounts.application.errors import InvalidCredential
from accounts.composition import container

User = get_user_model()


def _providers_for(user) -> list[str]:
    providers: list[str] = ["password"] if user.has_usable_password() else []
    for provider in (
        ExternalIdentityModel.objects.filter(user=user)
        .values_list("provider", flat=True)
        .distinct()
    ):
        if provider not in providers:
            providers.append(provider)
    return providers


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

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


class GoogleAuthView(APIView):
    """Exchange a Google ID token for our JWT, provisioning the account if new."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        credential = request.data.get("id_token")
        if not credential:
            raise ValidationError({"id_token": "required"})
        try:
            account = container.build_authenticate_with_google().execute(credential)
        except InvalidCredential:
            return Response({"detail": "Не удалось подтвердить токен Google."}, status=401)
        refresh = RefreshToken.for_user(User.objects.get(pk=account.id))
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": account.id,
                    "username": account.username,
                    "email": account.email,
                    "providers": list(account.providers),
                },
            },
            status=200,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email or None,
                "providers": _providers_for(request.user),
            }
        )


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

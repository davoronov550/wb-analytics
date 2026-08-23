from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.adapters.inbound.http.views import (
    GoogleAuthView,
    LogoutView,
    MeView,
    RegisterView,
    SavedSearchDetailView,
    SavedSearchListView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/google/", GoogleAuthView.as_view(), name="google-auth"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("saved-searches/", SavedSearchListView.as_view(), name="saved-search-list"),
    path(
        "saved-searches/<int:saved_id>/",
        SavedSearchDetailView.as_view(),
        name="saved-search-detail",
    ),
]

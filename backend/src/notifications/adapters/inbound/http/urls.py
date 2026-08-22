from django.urls import path

from notifications.adapters.inbound.http.views import AlertDetailView, AlertListView

urlpatterns = [
    path("alerts/", AlertListView.as_view(), name="alert-list"),
    path("alerts/<int:rule_id>/", AlertDetailView.as_view(), name="alert-detail"),
]

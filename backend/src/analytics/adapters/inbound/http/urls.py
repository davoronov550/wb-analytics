from django.urls import path

from analytics.adapters.inbound.http.views import HistoryView, StatsView

urlpatterns = [
    path("products/<int:wb_id>/history/", HistoryView.as_view(), name="product-history"),
    path("stats/", StatsView.as_view(), name="stats"),
]

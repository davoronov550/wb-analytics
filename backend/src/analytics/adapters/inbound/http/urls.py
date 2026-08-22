from django.urls import path

from analytics.adapters.inbound.http.views import ExportView, HistoryView, StatsView

urlpatterns = [
    path("products/<int:wb_id>/history/", HistoryView.as_view(), name="product-history"),
    path("stats/", StatsView.as_view(), name="stats"),
    path("export/", ExportView.as_view(), name="export"),
]

from django.urls import path

from analytics.adapters.inbound.http.views import HistoryView

urlpatterns = [
    path("products/<int:wb_id>/history/", HistoryView.as_view(), name="product-history"),
]

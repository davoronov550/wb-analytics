"""Catalog HTTP adapter URLConf (mounted under /api/ by config.urls)."""

from __future__ import annotations

from django.urls import path

from catalog.adapters.inbound.http.views import ProductListView

urlpatterns = [
    path("products/", ProductListView.as_view(), name="products-list"),
]

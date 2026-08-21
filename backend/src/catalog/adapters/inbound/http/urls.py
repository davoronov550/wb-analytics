"""Catalog HTTP adapter URLConf (mounted under /api/ by config.urls)."""

from __future__ import annotations

from django.urls import path

from catalog.adapters.inbound.http.views import ParseView, ProductListView, TaskStatusView

urlpatterns = [
    path("products/", ProductListView.as_view(), name="products-list"),
    path("parse/", ParseView.as_view(), name="parse"),
    path("tasks/<str:task_id>/", TaskStatusView.as_view(), name="task-status"),
]

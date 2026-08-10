"""Tests for the DRF exception handler mapping (T020) — no DB needed."""

from catalog.adapters.inbound.http.exceptions import exception_handler
from catalog.application.errors import InvalidFilter, UpstreamUnavailable


def test_upstream_unavailable_maps_to_502_without_leak():
    resp = exception_handler(UpstreamUnavailable("connect timeout to search.wb.ru"), context={})
    assert resp is not None
    assert resp.status_code == 502
    assert resp.data == {"detail": "Upstream Wildberries request failed."}


def test_invalid_filter_maps_to_400():
    resp = exception_handler(InvalidFilter("min_price must be <= max_price"), context={})
    assert resp is not None
    assert resp.status_code == 400
    assert "min_price" in resp.data["detail"]


def test_unhandled_non_drf_error_falls_through_to_default():
    # A plain ValueError is not a DRF exception, so the default handler returns None
    # (DRF then renders it as a 500 — no leaked internals in production).
    assert exception_handler(ValueError("boom"), context={}) is None

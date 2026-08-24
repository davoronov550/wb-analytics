"""Health endpoint test — reports check structure (infra may be down)."""

from rest_framework.test import APIClient


def test_health_reports_status_and_checks():
    resp = APIClient().get("/api/health/")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert set(body["checks"]) == {"database", "redis"}

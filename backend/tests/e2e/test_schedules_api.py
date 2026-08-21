"""E2E tests (T063) for /api/schedules/ (FE-01).

Validation 400s run offline; the CRUD flow needs the DB (@django_db, deferred).
"""

import pytest
from rest_framework.test import APIClient


def test_missing_fields_returns_400():
    resp = APIClient().post("/api/schedules/", {"query": "наушники"}, format="json")
    assert resp.status_code == 400


def test_invalid_spec_returns_400():
    # ManageSchedules parses the spec before any DB access, so this stays offline.
    resp = APIClient().post("/api/schedules/", {"query": "q", "spec": "whenever"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_list_toggle_delete_flow():
    client = APIClient()

    created = client.post(
        "/api/schedules/", {"query": "наушники", "spec": "every 6h"}, format="json"
    )
    assert created.status_code == 201
    schedule_id = created.data["id"]
    assert created.data["interval_seconds"] == 21600
    assert created.data["active"] is True

    listed = client.get("/api/schedules/")
    assert any(s["id"] == schedule_id for s in listed.data)

    disabled = client.patch(f"/api/schedules/{schedule_id}/", {"active": False}, format="json")
    assert disabled.status_code == 200
    assert disabled.data["active"] is False

    removed = client.delete(f"/api/schedules/{schedule_id}/")
    assert removed.status_code == 204


@pytest.mark.django_db
def test_patch_unknown_schedule_returns_404():
    resp = APIClient().patch("/api/schedules/999999/", {"active": False}, format="json")
    assert resp.status_code == 404

"""E2E tests for /api/schedules/ (FE-01, owner-scoped per FE-09).

Auth 401 + validation 400 run offline (forced auth with an unsaved user reaches
validation without touching the DB). CRUD + owner isolation need the DB (@django_db).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


def test_requires_authentication():
    resp = APIClient().post(
        "/api/schedules/", {"query": "наушники", "spec": "every 6h"}, format="json"
    )
    assert resp.status_code == 401


def _auth_client(user=None):
    client = APIClient()
    client.force_authenticate(user=user or User(id=1, username="tester"))
    return client


def test_missing_fields_returns_400():
    resp = _auth_client().post("/api/schedules/", {"query": "наушники"}, format="json")
    assert resp.status_code == 400


def test_invalid_spec_returns_400():
    resp = _auth_client().post("/api/schedules/", {"query": "q", "spec": "whenever"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_create_list_toggle_delete_flow():
    user = User.objects.create_user(username="u1", password="pw123456")
    client = _auth_client(user)

    created = client.post(
        "/api/schedules/", {"query": "наушники", "spec": "every 6h"}, format="json"
    )
    assert created.status_code == 201
    schedule_id = created.data["id"]
    assert created.data["interval_seconds"] == 21600

    assert any(s["id"] == schedule_id for s in client.get("/api/schedules/").data)
    assert (
        client.patch(f"/api/schedules/{schedule_id}/", {"active": False}, format="json").data[
            "active"
        ]
        is False
    )
    assert client.delete(f"/api/schedules/{schedule_id}/").status_code == 204


@pytest.mark.django_db
def test_owner_isolation():
    owner = User.objects.create_user(username="owner", password="pw123456")
    other = User.objects.create_user(username="other", password="pw123456")
    created = _auth_client(owner).post(
        "/api/schedules/", {"query": "наушники", "spec": "every 6h"}, format="json"
    )
    schedule_id = created.data["id"]

    other_client = _auth_client(other)
    assert other_client.get("/api/schedules/").data == []
    assert (
        other_client.patch(
            f"/api/schedules/{schedule_id}/", {"active": False}, format="json"
        ).status_code
        == 404
    )
    assert other_client.delete(f"/api/schedules/{schedule_id}/").status_code == 404

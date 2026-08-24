"""E2E tests for /api/alerts/ (owner-scoped).

401 without auth runs offline; CRUD + owner isolation need the DB (@django_db).
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

_BODY = {
    "target": {"wb_id": 179421376},
    "condition": {"kind": "abs_below", "value": 2500},
    "channel": "email",
}


def test_requires_authentication():
    resp = APIClient().post("/api/alerts/", _BODY, format="json")
    assert resp.status_code == 401


def _auth(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_create_list_delete_flow():
    client = _auth(User.objects.create_user(username="u1", password="pw123456"))

    created = client.post("/api/alerts/", _BODY, format="json")
    assert created.status_code == 201
    rule_id = created.data["id"]
    assert created.data["kind"] == "abs_below"

    assert any(r["id"] == rule_id for r in client.get("/api/alerts/").data)
    assert client.delete(f"/api/alerts/{rule_id}/").status_code == 204


@pytest.mark.django_db
def test_bad_kind_returns_400():
    client = _auth(User.objects.create_user(username="u2", password="pw123456"))
    resp = client.post(
        "/api/alerts/",
        {"target": {"query": "q"}, "condition": {"kind": "nope", "value": 1}, "channel": "email"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_owner_isolation():
    owner = User.objects.create_user(username="owner", password="pw123456")
    other = User.objects.create_user(username="other", password="pw123456")
    rule_id = _auth(owner).post("/api/alerts/", _BODY, format="json").data["id"]

    other_client = _auth(other)
    assert other_client.get("/api/alerts/").data == []
    assert other_client.delete(f"/api/alerts/{rule_id}/").status_code == 404

"""E2E auth + saved-search isolation — requires DB (@django_db, deferred).

Auth 401 for a protected endpoint runs offline.
"""

import pytest
from rest_framework.test import APIClient


def test_saved_searches_require_auth():
    resp = APIClient().get("/api/saved-searches/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_register_login_and_saved_search_isolation():
    client = APIClient()

    # Register two users.
    assert (
        client.post(
            "/api/auth/register/", {"username": "alice", "password": "pw123456"}, format="json"
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/auth/register/", {"username": "bob", "password": "pw123456"}, format="json"
        ).status_code
        == 201
    )

    def token(username):
        resp = client.post(
            "/api/auth/login/", {"username": username, "password": "pw123456"}, format="json"
        )
        assert resp.status_code == 200
        return resp.data["access"]

    alice = APIClient()
    alice.credentials(HTTP_AUTHORIZATION=f"Bearer {token('alice')}")
    bob = APIClient()
    bob.credentials(HTTP_AUTHORIZATION=f"Bearer {token('bob')}")

    created = alice.post(
        "/api/saved-searches/",
        {"name": "Наушники дешево", "query": "наушники", "filters": {"minRating": 4}},
        format="json",
    )
    assert created.status_code == 201
    saved_id = created.data["id"]

    # Bob sees none of Alice's and cannot delete hers.
    assert bob.get("/api/saved-searches/").data == []
    assert bob.delete(f"/api/saved-searches/{saved_id}/").status_code == 404
    # Alice sees her own.
    assert [s["id"] for s in alice.get("/api/saved-searches/").data] == [saved_id]

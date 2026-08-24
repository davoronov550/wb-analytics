"""E2E Google sign-in (@django_db, deferred) — offline via a fake verifier.

The HTTP + directory + JWT path is exercised end to end; only the Google network
verification is replaced ( deterministic, offline).
"""

import pytest
from rest_framework.test import APIClient

from accounts.adapters.inbound.http import views
from accounts.adapters.outbound.persistence.user_directory import DjangoUserDirectory
from accounts.application.dto import VerifiedIdentity
from accounts.application.use_cases.authenticate_with_provider import AuthenticateWithProvider


class _FakeVerifier:
    def __init__(self, identity: VerifiedIdentity):
        self._identity = identity

    def verify(self, credential: str) -> VerifiedIdentity | None:
        return self._identity if credential == "good-token" else None


def _install_fake(monkeypatch, identity: VerifiedIdentity) -> None:
    def build() -> AuthenticateWithProvider:
        return AuthenticateWithProvider(
            verifier=_FakeVerifier(identity), directory=DjangoUserDirectory()
        )

    monkeypatch.setattr(views.container, "build_authenticate_with_google", build)


IDENTITY = VerifiedIdentity(provider="google", external_id="sub-9", email="gio@x.io", name="Gio")


def test_google_endpoint_requires_id_token():
    assert APIClient().post("/api/auth/google/", {}, format="json").status_code == 400


@pytest.mark.django_db
def test_google_login_rejects_invalid_token(monkeypatch):
    _install_fake(monkeypatch, IDENTITY)
    resp = APIClient().post("/api/auth/google/", {"id_token": "nope"}, format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_google_login_provisions_account_and_issues_jwt(monkeypatch):
    _install_fake(monkeypatch, IDENTITY)
    client = APIClient()

    resp = client.post("/api/auth/google/", {"id_token": "good-token"}, format="json")
    assert resp.status_code == 200
    assert resp.data["access"]
    assert resp.data["user"]["email"] == "gio@x.io"
    assert resp.data["user"]["providers"] == ["google"]

    # The issued token works and /me reports the linked provider.
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    me = client.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == "gio@x.io"
    assert me.data["providers"] == ["google"]

    # A second login with the same identity reuses the account (idempotent).
    again = APIClient().post("/api/auth/google/", {"id_token": "good-token"}, format="json")
    assert again.data["user"]["id"] == resp.data["user"]["id"]

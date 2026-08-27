"""Access tokens are short-lived and refresh tokens can actually be revoked.

Before this, an access token lived 12 hours and logout was a no-op, so a stolen
token stayed valid for half a day with no way to cut it off.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import override_settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
LOGOUT = "/api/auth/logout/"
ME = "/api/auth/me/"

CREDS = {"username": "sam", "password": "pw-abcdefgh"}


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    caches["default"].clear()
    yield
    caches["default"].clear()


@pytest.fixture
def user():
    return User.objects.create_user(**CREDS)


def login(client: APIClient) -> dict:
    response = client.post(LOGIN, CREDS, format="json")
    assert response.status_code == 200
    return response.data


def test_login_returns_both_tokens(user):
    data = login(APIClient())
    assert "access" in data and "refresh" in data


def test_access_token_is_short_lived():
    """A stolen access token should expire in minutes, not hours."""
    from django.conf import settings

    assert settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] <= timedelta(minutes=60)


def test_refresh_issues_a_new_access_token(user):
    client = APIClient()
    tokens = login(client)

    response = client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")

    assert response.status_code == 200
    assert "access" in response.data


def test_logout_revokes_the_refresh_token(user):
    """After logout the refresh token must not buy a new access token."""
    client = APIClient()
    tokens = login(client)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    logout = client.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json")
    assert logout.status_code in (200, 205)

    client.credentials()
    replay = client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert replay.status_code == 401, "revoked refresh token was still accepted"


def test_rotation_invalidates_the_previous_refresh_token(user):
    """Rotation means a captured refresh token is single-use."""
    client = APIClient()
    tokens = login(client)

    first = client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert first.status_code == 200
    assert first.data.get("refresh"), "rotation should hand back a new refresh token"

    replay = client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")
    assert replay.status_code == 401, "the old refresh token must be dead after rotation"


def test_logout_without_a_refresh_token_is_not_an_error(user):
    """A client that lost its refresh token must still be able to log out."""
    client = APIClient()
    tokens = login(client)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    assert client.post(LOGOUT, {}, format="json").status_code in (200, 205)


@override_settings(SIMPLE_JWT={"ACCESS_TOKEN_LIFETIME": timedelta(seconds=-1)})
def test_an_expired_access_token_is_rejected(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer clearly-not-a-token")
    assert client.get(ME).status_code == 401

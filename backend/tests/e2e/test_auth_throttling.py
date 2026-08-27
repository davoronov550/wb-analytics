"""Auth endpoints must resist brute force.

The `auth` throttle scope was configured but never attached to a view, so login
accepted unlimited guesses. These tests pin the fix.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import override_settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()
LOGIN = "/api/auth/login/"
REGISTER = "/api/auth/register/"
GOOGLE = "/api/auth/google/"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Throttle counters live in the cache; isolate every test."""
    caches["default"].clear()
    yield
    caches["default"].clear()


@override_settings(REST_FRAMEWORK_THROTTLE_AUTH="5/min")
def test_repeated_failed_logins_are_throttled():
    client = APIClient()
    statuses = [
        client.post(LOGIN, {"username": "nobody", "password": "wrong"}, format="json").status_code
        for _ in range(12)
    ]
    assert 429 in statuses, f"brute force was not throttled: {statuses}"


def test_a_legitimate_login_within_the_limit_still_works():
    User.objects.create_user(username="alice", password="correct-horse-1")
    client = APIClient()

    response = client.post(
        LOGIN, {"username": "alice", "password": "correct-horse-1"}, format="json"
    )

    assert response.status_code == 200
    assert "access" in response.data


def test_registration_is_throttled():
    client = APIClient()
    statuses = [
        client.post(
            REGISTER, {"username": f"user{i}", "password": "pw-abcdefgh"}, format="json"
        ).status_code
        for i in range(15)
    ]
    assert 429 in statuses, f"registration flood was not throttled: {statuses}"


def test_google_exchange_is_throttled():
    client = APIClient()
    statuses = [
        client.post(GOOGLE, {"id_token": "bogus"}, format="json").status_code for _ in range(15)
    ]
    assert 429 in statuses, f"google token guessing was not throttled: {statuses}"

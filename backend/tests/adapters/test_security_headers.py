"""Content-Security-Policy on Django-served responses.

Django serves the JSON API and the HTML admin. CSP matters for the HTML surface
(the admin); on JSON it is defence in depth and costs nothing.
"""

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db

HEADER = "Content-Security-Policy"


def test_csp_header_is_present():
    response = Client().get("/api/health/")
    assert HEADER in response.headers


def test_csp_locks_down_the_dangerous_directives():
    policy = Client().get("/api/health/").headers[HEADER]
    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "base-uri 'self'" in policy


def test_csp_allows_google_identity_services():
    """The SPA signs in with GIS, which loads from accounts.google.com."""
    policy = Client().get("/api/health/").headers[HEADER]
    assert "https://accounts.google.com" in policy


@override_settings(CSP_POLICY="default-src 'none'")
def test_policy_is_configurable():
    assert Client().get("/api/health/").headers[HEADER] == "default-src 'none'"


@override_settings(CSP_POLICY="")
def test_empty_policy_disables_the_header():
    assert HEADER not in Client().get("/api/health/").headers

"""A NUL byte in a request body is refused, not stored (T053).

PostgreSQL holds no NUL (0x00) in `text` or `jsonb`, while JSON strings and
Python `str` carry it happily. So every text field in the API is a 500 waiting
for a client that sends one, and the fuzzer found two of them — `query` on the
collection endpoint and a value inside `filters` on saved searches.

Fixed once at the boundary rather than per field. By the time these two
appeared, five out-of-range values had already been fixed one at a time, each
uncovered by the previous fix; a rule that holds for every text field in the
API is the only version of this that ends.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

NUL = "\x00"


def _auth(username: str) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user(username=username, password="pw123456"))
    return client


class TestNulIsRefused:
    @pytest.mark.django_db
    def test_in_a_top_level_string(self):
        response = APIClient().post("/api/parse/", {"query": f"phone{NUL}"}, format="json")

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_nested_inside_a_json_field(self):
        """`filters` is jsonb, which rejects the escape rather than the byte."""
        response = _auth("nul-nested").post(
            "/api/saved-searches/",
            {"name": "n", "query": "q", "filters": {"min_price": f"1{NUL}"}},
            format="json",
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_in_a_key(self):
        response = _auth("nul-key").post(
            "/api/saved-searches/",
            {"name": "n", "query": "q", "filters": {f"k{NUL}": "1"}},
            format="json",
        )

        assert response.status_code == 400

    def test_the_response_is_an_envelope_not_a_crash(self):
        response = APIClient().post("/api/parse/", {"query": NUL}, format="json")

        assert response.status_code == 400
        assert "detail" in response.json()


class TestOrdinaryBodiesStillWork:
    """A boundary check that rejects too much is worse than the defect."""

    @pytest.mark.django_db
    def test_a_body_with_unicode_but_no_nul(self):
        response = APIClient().post(
            "/api/parse/", {"query": "наушники — беспроводные 🎧"}, format="json"
        )

        assert response.status_code == 202

    @pytest.mark.django_db
    def test_an_escaped_backslash_u_that_is_not_a_nul(self):
        """`\u0000` written literally by the client is text, not a NUL."""
        body = json.dumps({"query": r"literal \u0000 in text"})
        response = APIClient().post("/api/parse/", body, content_type="application/json")

        assert response.status_code == 202

    @pytest.mark.django_db
    def test_a_get_with_no_body_is_untouched(self):
        assert APIClient().get("/api/products/").status_code == 200

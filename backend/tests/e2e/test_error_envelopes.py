"""Every error under /api/ answers with JSON (T053).

Two gaps a contract run found, both invisible from inside DRF:

`/api/schedules/<int:id>/` does not match a non-numeric id, so the request
leaves the URL resolver before any view runs. Django then renders its HTML error
page — inside `/api/`, to a client that asked for JSON. Nothing in the DRF stack
sees the request, so the shared exception handler cannot help.

The alert delete returned a bare 404 with no body while its two siblings
returned an envelope, and the schema declared one for all three. A client
decoding the response failed on the decode instead of reading the status.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def production_like(settings):
    """`handler404` is only consulted when DEBUG is off; with DEBUG on Django
    serves the technical 404 page and the test would pass against nothing."""
    settings.DEBUG = False
    return settings


def _auth(username: str) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user(username=username, password="pw123456"))
    return client


class TestUnroutableApiPath:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/schedules/not-a-number/",
            "/api/products/not-a-number/history/",
            "/api/alerts/not-a-number/",
            "/api/no-such-endpoint/",
        ],
    )
    def test_answers_json_not_html(self, production_like, path: str) -> None:
        response = APIClient().get(path)

        assert response.status_code == 404
        assert response["Content-Type"].startswith("application/json")
        assert response.json() == {"detail": "Not found."}

    def test_paths_outside_the_api_keep_djangos_page(self, production_like) -> None:
        """The admin is read by browsers; an envelope there would be a
        regression, not a fix."""
        response = APIClient().get("/no-such-page/")

        assert response.status_code == 404
        assert not response["Content-Type"].startswith("application/json")


class TestDeleteNotFoundCarriesABody:
    """All three deletes declare an envelope for 404. One did not send it."""

    @pytest.mark.django_db
    def test_alert_delete_of_a_missing_rule(self) -> None:
        response = _auth("alert-404").delete("/api/alerts/999999/")

        assert response.status_code == 404
        assert response.json() == {"detail": "Not found."}

    @pytest.mark.django_db
    def test_saved_search_delete_of_a_missing_row(self) -> None:
        response = _auth("saved-404").delete("/api/saved-searches/999999/")

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.django_db
    def test_schedule_delete_of_a_missing_row(self) -> None:
        response = _auth("sched-404").delete("/api/schedules/999999/")

        assert response.status_code == 404
        assert "detail" in response.json()


class TestSavedSearchFiltersMustBeAnObject:
    """`filters` is declared as an object in the contract, and `JSONField`
    accepted a list — which then came back out of the list endpoint and broke
    the response against the same schema. The write end and the read end have
    to agree, and only one of them was checked."""

    @pytest.mark.django_db
    def test_a_list_is_refused(self) -> None:
        response = _auth("filters-list").post(
            "/api/saved-searches/",
            {"name": "n", "query": "q", "filters": [None, None]},
            format="json",
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_an_object_is_accepted(self) -> None:
        response = _auth("filters-object").post(
            "/api/saved-searches/",
            {"name": "n", "query": "q", "filters": {"min_price": "100"}},
            format="json",
        )

        assert response.status_code == 201

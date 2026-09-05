"""`/v1/` answers exactly what `/api/` answers (T065).

The alias exists so the cutover to the FastAPI gateway is a routing change and
not an API change: clients move to `/v1/` while Django still serves it, and when
the gateway takes the prefix over, the path they send is already the right one.

That only holds while the two prefixes stay identical. `config.urls` mounts
both from one list of contexts, so a route added *inside* a context appears
under both by construction — a mutation that drops a context from that list
leaves the two sets equal, and this test correctly stays green.

What it does catch is a route mounted on `/api/` directly, outside that loop,
which is how `api/health/` already got there. The next such line is likelier to
be an endpoint that should have been versioned, and it would otherwise be
missing from `/v1/` until a client hit it.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import get_resolver
from rest_framework.test import APIClient

User = get_user_model()

_PREFIXES = ("/api", "/v1")


def _routes_under(prefix: str) -> set[tuple[str, str]]:
    """(path without the prefix, view name) for every route under `prefix`."""
    routes: set[tuple[str, str]] = set()

    def walk(patterns, base: str) -> None:
        for entry in patterns:
            path = base + str(entry.pattern)
            nested = getattr(entry, "url_patterns", None)
            if nested is not None:
                walk(nested, path)
            elif path.startswith(prefix.lstrip("/")):
                view = entry.callback
                name = getattr(view, "view_class", view).__name__
                routes.add((path[len(prefix.lstrip("/")) :], name))

    walk(get_resolver().url_patterns, "")
    return routes


class TestTheTwoPrefixesAreOneApi:
    def test_every_api_route_has_a_v1_twin_on_the_same_view(self) -> None:
        api = _routes_under("/api")
        v1 = _routes_under("/v1")

        # `api/health/` is deliberately unversioned: liveness is infrastructure,
        # and the gateway answers its own.
        api.discard(("/health/", "health_view"))

        assert api == v1, f"only under /api: {api - v1}; only under /v1: {v1 - api}"

    def test_the_comparison_can_actually_fail(self) -> None:
        """Guards the guard: a walker that returns an empty set would report
        two prefixes as identical while finding neither."""
        assert _routes_under("/api"), "route walker found nothing under /api"


class TestBehaviourIsIdentical:
    """Spot checks across the response kinds the alias has to preserve:
    a public read, an authenticated read, a validation error and a 404."""

    @pytest.mark.django_db
    @pytest.mark.parametrize("prefix", _PREFIXES)
    def test_public_read(self, prefix: str) -> None:
        response = APIClient().get(f"{prefix}/products/?page_size=1")

        assert response.status_code == 200
        assert set(response.json()) == {"count", "next", "previous", "results"}

    @pytest.mark.parametrize("prefix", _PREFIXES)
    def test_authentication_is_required_where_it_was(self, prefix: str) -> None:
        """An alias that quietly dropped the permission classes would still
        return 200 here, which is why this asserts the refusal."""
        assert APIClient().get(f"{prefix}/alerts/").status_code == 401

    @pytest.mark.django_db
    @pytest.mark.parametrize("prefix", _PREFIXES)
    def test_authenticated_read(self, prefix: str) -> None:
        client = APIClient()
        client.force_authenticate(user=User.objects.create_user(username=f"u{prefix[1:]}"))

        assert client.get(f"{prefix}/alerts/").status_code == 200

    @pytest.mark.parametrize("prefix", _PREFIXES)
    def test_validation_error_shape(self, prefix: str) -> None:
        response = APIClient().get(f"{prefix}/products/?page=0")

        assert response.status_code == 400
        assert "detail" in response.json()

    @pytest.mark.parametrize("prefix", _PREFIXES)
    def test_unroutable_path_answers_json(self, prefix: str, settings) -> None:
        """`handler404` keys off the prefix, so the new one had to be added to
        it — otherwise `/v1/` would answer HTML where `/api/` answers an
        envelope."""
        settings.DEBUG = False
        response = APIClient().get(f"{prefix}/schedules/not-a-number/")

        assert response.status_code == 404
        assert response["Content-Type"].startswith("application/json")
        assert response.json() == {"detail": "Not found."}


class TestTheAliasStaysOutOfTheContract:
    """`contracts/openapi/v1.yaml` is the frozen reference the migration is
    checked against, and it describes one prefix.

    Without the preprocessing hook the alias mounts are collected too, and
    drf-spectacular resolves the duplicate operationIds by appending `_2`
    rather than failing — so the contract would silently grow a second, weakly
    named copy of every operation, and generated clients would carry both.
    """

    def test_no_v1_path_reaches_the_schema(self) -> None:
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        aliased = [path for path in schema["paths"] if path.startswith("/v1/")]

        assert not aliased, f"alias paths leaked into the contract: {aliased}"

    def test_every_operation_id_is_unique(self) -> None:
        """The symptom the hook prevents, asserted directly: a `_2` suffix is
        how the collision resolves, and it is easy to miss in a 1500-line file."""
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(request=None, public=True)
        ids = [
            operation["operationId"]
            for methods in schema["paths"].values()
            for operation in methods.values()
        ]

        assert len(ids) == len(set(ids)), f"duplicate operationIds: {sorted(ids)}"

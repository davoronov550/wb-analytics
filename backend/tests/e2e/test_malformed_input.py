"""Malformed request bodies get 400, not 500 (T053).

Every case here was found by fuzzing the frozen contract with schemathesis,
not by review. All three share one shape: untrusted input reaches an attribute
access or a column write without a type or length check at the boundary, and
Django answers with an unhandled 500 — a status the contract never declares.

The alerts case is the instructive one. The view already guards the body with
`isinstance(request.data, Mapping)`, so the author knew the risk; the guard was
just applied one level too shallow, and `condition` a level down was still
taken on faith. A guard that stops at the outermost object reads as protection
while the actual attribute access sits underneath it.

Kept as a named regression suite because the same three validations have to
exist in the services that replace these endpoints; a green test is how the
target inherits them instead of the defect.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

#: `ParseJobModel.query` is CharField(max_length=200). 200 was accepted before
#: the fix and 201 raised DataError from PostgreSQL, so the boundary is exact.
_QUERY_LIMIT = 200


def _auth(username: str) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user(username=username, password="pw123456"))
    return client


class TestNoUnhandledServerError:
    """The three bodies that produced a 500. Each asserts a specific status:
    `< 500` would pass on a 404 from a typo in the path."""

    def test_google_login_rejects_a_body_that_is_not_an_object(self):
        """`request.data.get` on a list is an AttributeError, and nothing
        catches it — the endpoint is unauthenticated, so the 500 is reachable
        by anyone."""
        resp = APIClient().post("/api/auth/google/", [None, None], format="json")

        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_alert_rejects_a_condition_that_is_not_an_object(self):
        """The outer Mapping guard does not reach `condition.get`."""
        resp = _auth("malformed-condition").post(
            "/api/alerts/",
            {"condition": "not-an-object", "channel": "email", "target": {}},
            format="json",
        )

        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_alert_rejects_a_target_that_is_not_an_object(self):
        """`target` is read the same way and was missing the same guard."""
        resp = _auth("malformed-target").post(
            "/api/alerts/",
            {"condition": {"kind": "abs_below", "value": 2500}, "channel": "email", "target": "x"},
            format="json",
        )

        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_collection_rejects_a_query_longer_than_the_column(self):
        """Without a length check the row reaches PostgreSQL and DataError
        surfaces as a 500 after the request was accepted as valid."""
        resp = APIClient().post(
            "/api/parse/", {"query": "0" * (_QUERY_LIMIT + 1)}, format="json"
        )

        assert resp.status_code == 400


class TestTheLimitIsNotOffByOne:
    """A length check is as easy to write one short as one long, and either
    way the failure is invisible until a real query sits on the boundary."""

    @pytest.mark.django_db
    def test_a_query_at_the_column_width_is_still_accepted(self):
        resp = APIClient().post("/api/parse/", {"query": "0" * _QUERY_LIMIT}, format="json")

        assert resp.status_code == 202


class TestValuesTooLargeForTheirColumn:
    """The same defect as the over-long query, one column over.

    `target_wb_id` is a BigIntegerField, so PostgreSQL refuses anything outside
    the signed 64-bit range. The view accepted it and the INSERT raised, which
    reached the client as a 500 for input the API should have refused. It was
    only reachable once the malformed-`condition` guard above stopped rejecting
    these bodies earlier — one defect was hiding the next.
    """

    #: What a PostgreSQL `bigint` holds.
    _BIGINT_MAX = 2**63 - 1

    def _body(self, wb_id: int) -> dict:
        return {
            "condition": {"kind": "abs_below", "value": "2500"},
            "target": {"wb_id": wb_id},
            "channel": "email",
        }

    @pytest.mark.django_db
    def test_a_wb_id_beyond_the_column_is_refused(self):
        response = _auth("wb-id-too-large").post(
            "/api/alerts/", self._body(self._BIGINT_MAX + 1), format="json"
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_a_negative_wb_id_beyond_the_column_is_refused(self):
        """The value that actually surfaced this: a large negative one."""
        response = _auth("wb-id-too-small").post(
            "/api/alerts/", self._body(-542521149567307153408), format="json"
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_a_wb_id_at_the_edge_is_still_accepted(self):
        response = _auth("wb-id-edge").post(
            "/api/alerts/", self._body(self._BIGINT_MAX), format="json"
        )

        assert response.status_code == 201


class TestDecimalsTooLargeForTheirColumn:
    """The third value in this API that passes the view and dies at the column.

    `AlertRuleModel.value` is DECIMAL(10, 2), so PostgreSQL holds at most
    99999999.99. The view coerced anything `Decimal(str(...))` accepted and
    handed it straight to the INSERT, which raised `numeric field overflow`.

    It only surfaced after the two fixes above stopped rejecting these bodies
    earlier — the same sequence as `wb_id`. Worth stating plainly: three
    columns in this API were reachable with an out-of-range value, and each one
    was hidden behind the previous.
    """

    #: DECIMAL(10, 2) — eight digits before the point, two after.
    _LARGEST = "99999999.99"

    def _body(self, value: str) -> dict:
        return {
            "condition": {"kind": "abs_below", "value": value},
            "target": {"wb_id": 179421376},
            "channel": "email",
        }

    @pytest.mark.django_db
    def test_a_value_beyond_the_column_is_refused(self):
        response = _auth("value-too-large").post(
            "/api/alerts/", self._body("100000000.00"), format="json"
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_a_hugely_negative_value_is_refused(self):
        response = _auth("value-too-small").post(
            "/api/alerts/", self._body("-1e30"), format="json"
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_the_largest_representable_value_is_accepted(self):
        response = _auth("value-edge").post(
            "/api/alerts/", self._body(self._LARGEST), format="json"
        )

        assert response.status_code == 201

    @pytest.mark.django_db
    def test_more_decimal_places_than_the_column_holds_are_refused(self):
        """Rounding silently would change the threshold the user asked for."""
        response = _auth("value-precision").post(
            "/api/alerts/", self._body("1.005"), format="json"
        )

        assert response.status_code == 400


class TestStringsTooLongForTheirColumn:
    """`AlertRuleModel.target_query` is varchar(200) and the view passed it
    through untouched.

    Fourth column in this API reachable with an out-of-range value, and the
    reason they keep appearing is structural: the view validates the body by
    hand, so `AlertTargetSerializer`'s `max_length=200` only ever describes the
    schema and never runs. Every constraint has to be restated in the view, and
    each one that is not becomes a 500.
    """

    @pytest.mark.django_db
    def test_a_target_query_longer_than_the_column_is_refused(self):
        response = _auth("target-query-long").post(
            "/api/alerts/",
            {
                "condition": {"kind": "abs_below", "value": "2500"},
                "target": {"query": "0" * 201},
                "channel": "email",
            },
            format="json",
        )

        assert response.status_code == 400

    @pytest.mark.django_db
    def test_a_target_query_at_the_column_width_is_accepted(self):
        response = _auth("target-query-edge").post(
            "/api/alerts/",
            {
                "condition": {"kind": "abs_below", "value": "2500"},
                "target": {"query": "0" * 200},
                "channel": "email",
            },
            format="json",
        )

        assert response.status_code == 201


class TestTheLimitTracksTheColumn:
    """A hand-written length check and a column width are two copies of one
    number. Widening the column without the view reintroduces the 500;
    narrowing it without the view does the same. Neither is visible in review."""

    def test_the_view_limit_equals_the_column_width(self):
        from catalog.adapters.inbound.http.views import _MAX_PARSE_QUERY
        from catalog.adapters.outbound.persistence.models import ParseJobModel

        column = ParseJobModel._meta.get_field("query").max_length

        assert _MAX_PARSE_QUERY == column
        assert _QUERY_LIMIT == column  # and the fixture above tests the real edge

    def test_the_declared_schema_limit_equals_the_column_width(self):
        """A third copy of the same number: the serializer that describes this
        body in the frozen contract. If it drifts, the published contract
        promises a length the API refuses."""
        from catalog.adapters.inbound.http.serializers import ParseRequestSerializer
        from catalog.adapters.outbound.persistence.models import ParseJobModel

        declared = ParseRequestSerializer().fields["query"].max_length

        assert declared == ParseJobModel._meta.get_field("query").max_length


class TestFilterValuesTooLargeForTheirColumn:
    """The same defect on a read path.

    A filter value is not stored, so it looked exempt — but it still reaches
    PostgreSQL, in the WHERE clause, and a comparison against a value wider
    than the column raises there just as an INSERT would. `min_reviews` did.

    Written as a sweep rather than one case because the previous six of these
    were found one at a time, each after fixing the one before. Every filter
    with a numeric column behind it is checked here at once.
    """

    _INT_MAX = 2**31 - 1  # PositiveIntegerField → PostgreSQL integer
    _DECIMAL_MAX = "99999999.99"  # DECIMAL(10, 2)

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        ("parameter", "value"),
        [
            ("min_reviews", str(2**31)),
            ("max_reviews", str(2**63)),
            ("min_price", "100000000.00"),
            ("max_price", "1e30"),
        ],
    )
    def test_a_filter_beyond_its_column_is_refused(self, parameter: str, value: str) -> None:
        response = APIClient().get(f"/api/products/?{parameter}={value}")

        assert response.status_code == 400

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        ("parameter", "value"),
        [
            ("min_reviews", "0"),
            ("max_reviews", str(_INT_MAX)),
            ("min_price", "0"),
            ("max_price", _DECIMAL_MAX),
        ],
    )
    def test_a_filter_at_the_edge_is_accepted(self, parameter: str, value: str) -> None:
        response = APIClient().get(f"/api/products/?{parameter}={value}")

        assert response.status_code == 200

    @pytest.mark.django_db
    def test_a_product_id_beyond_bigint_is_refused(self) -> None:
        """`<int:wb_id>` matches any run of digits, so the path carries the
        same risk as a body field."""
        response = APIClient().get(f"/api/products/{2**63}/history/")

        assert response.status_code in {400, 404}

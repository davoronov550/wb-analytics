"""Notifications HTTP views (inbound adapter) — owner-scoped alert CRUD."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.adapters.inbound.http.serializers import ErrorSerializer
from notifications.adapters.inbound.http.serializers import (
    AlertRuleSerializer,
    CreateAlertSerializer,
)
from notifications.composition import container

# `AlertRuleModel.target_query` is varchar(200). Same shape of defect as the two
# below, and the same cause: this view validates by hand, so `max_length` on
# `AlertTargetSerializer` describes the schema without ever running.
_TARGET_QUERY_MAX = 200


def _target_query(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationError({"detail": "target.query must be a string"})
    if len(raw) > _TARGET_QUERY_MAX:
        raise ValidationError(
            {"detail": f"target.query must be at most {_TARGET_QUERY_MAX} characters"}
        )
    return raw


# `AlertRuleModel.value` is DECIMAL(10, 2). Anything wider overflows the column
# and PostgreSQL raises `numeric field overflow` — a 500 for input the API
# should have refused. Third column in this API with that shape of defect, and
# each was hidden behind the previous one; `test_malformed_input` pins all three.
_VALUE_MAX_DIGITS = 10
_VALUE_DECIMAL_PLACES = 2


def _condition_value(raw: object) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError({"detail": "condition.value must be a number"}) from exc
    if not value.is_finite():
        raise ValidationError({"detail": "condition.value must be finite"})
    _, digits, exponent = value.as_tuple()
    exponent = int(exponent)
    # A positive exponent means the digits are scaled up, not down: `-1e30` is
    # DecimalTuple(digits=(1,), exponent=30), one digit and thirty-one integer
    # places. Reading only the negative case counts that as a single digit and
    # lets the overflow through — which is how it first slipped past this check.
    if exponent >= 0:
        places, integer_digits = 0, len(digits) + exponent
    else:
        places, integer_digits = -exponent, max(len(digits) + exponent, 0)
    if places > _VALUE_DECIMAL_PLACES:
        # Rounding here would silently change the threshold the user asked to
        # be alerted on, which is worse than refusing it.
        raise ValidationError({"detail": "condition.value allows at most 2 decimal places"})
    if integer_digits > _VALUE_MAX_DIGITS - _VALUE_DECIMAL_PLACES:
        raise ValidationError({"detail": "condition.value is out of range"})
    return value


# `AlertRuleModel.target_wb_id` is a BigIntegerField, so PostgreSQL refuses
# anything outside the signed 64-bit range. Checked here for the same reason the
# parse query length is: without it the row reaches the database, DataError
# surfaces as a 500, and the client is told the server broke on input the API
# should have refused.
_BIGINT_MIN = -(2**63)
_BIGINT_MAX = 2**63 - 1


def _target_wb_id(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)  # type: ignore[call-overload]
    except (ValueError, TypeError) as exc:
        raise ValidationError({"detail": "target.wb_id must be an integer"}) from exc
    if not (_BIGINT_MIN <= value <= _BIGINT_MAX):
        raise ValidationError({"detail": "target.wb_id is out of range"})
    return value


def _mapping(raw: object) -> Mapping:
    """A nested object, or an empty one — anything else is malformed input."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValidationError({"detail": "expected an object"})
    return raw


class AlertListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="alert_rules_list",
        summary="List the caller's alert rules",
        responses={200: AlertRuleSerializer(many=True), 401: ErrorSerializer},
    )
    def get(self, request: Request) -> Response:
        rules = container.build_manage_alerts().list(request.user.id)
        return Response(AlertRuleSerializer(rules, many=True).data)

    @extend_schema(
        operation_id="alert_rules_create",
        summary="Create an alert rule",
        # JSON only. `COMPONENT_SPLIT_REQUEST` otherwise advertises the two
        # form encodings as well, and neither can carry this body: a nested
        # object arrives as the string "{'kind': ...}" and a null as the
        # string "None". The API answers 400, correctly — the schema was
        # promising a media type that cannot work.
        request={"application/json": CreateAlertSerializer},
        responses={201: AlertRuleSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
    )
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, Mapping) else {}
        # The nested objects need the same guard as the body. Without it a
        # `condition` sent as a string reaches `.get` and raises AttributeError,
        # which nothing catches — the outer check reads as protection while the
        # actual attribute access sits a level below it.
        target = _mapping(data.get("target"))
        condition = _mapping(data.get("condition"))
        value = _condition_value(condition.get("value"))
        try:
            rule = container.build_manage_alerts().create(
                owner_id=request.user.id,
                kind=str(condition.get("kind")),
                value=value,
                channel=str(data.get("channel")),
                target_wb_id=_target_wb_id(target.get("wb_id")),
                target_query=_target_query(target.get("query")),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(AlertRuleSerializer(rule).data, status=201)


class AlertDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="alert_rules_destroy",
        summary="Delete an alert rule",
        responses={204: None, 401: ErrorSerializer, 404: ErrorSerializer},
    )
    def delete(self, request: Request, rule_id: int) -> Response:
        deleted = container.build_manage_alerts().delete(request.user.id, rule_id)
        if not deleted:
            # A body, like the sibling deletes: the schema declares an envelope
            # for this 404, and an empty response makes a client parsing it fail
            # on the decode rather than on the status.
            return Response({"detail": "Not found."}, status=404)
        return Response(status=204)

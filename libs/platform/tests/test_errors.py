"""Tests for the error model (T012).

The contract under test: one error hierarchy maps to both HTTP and gRPC, and
**nothing internal ever reaches the client** — not an exception message, not a
module path, not a SQL fragment.

The last part is the whole reason this module exists rather than each service
formatting its own errors. A leak here is a security finding, and it happens by
omission: someone returns ``str(exc)`` because it was convenient.
"""

from __future__ import annotations

import pytest

from wb_platform.errors import (
    ConflictError,
    FieldError,
    GrpcStatus,
    InternalError,
    NotFoundError,
    PermissionDeniedError,
    PlatformError,
    RateLimitedError,
    UnauthenticatedError,
    UpstreamUnavailableError,
    ValidationError,
    envelope_from_exception,
    to_envelope,
)
from wb_platform.logging import bind_context, clear_context


@pytest.fixture(autouse=True)
def _clean_context() -> None:
    clear_context()


class TestHttpMapping:
    @pytest.mark.parametrize(
        ("error", "status"),
        [
            (ValidationError("bad filter"), 400),
            (UnauthenticatedError("no token"), 401),
            (PermissionDeniedError("not yours"), 403),
            (NotFoundError("no such product"), 404),
            (ConflictError("already collected"), 409),
            (RateLimitedError("slow down"), 429),
            (InternalError("boom"), 500),
            (UpstreamUnavailableError("Wildberries down"), 502),
        ],
    )
    def test_error_maps_to_expected_status(self, error: PlatformError, status: int) -> None:
        assert error.http_status == status

    def test_filter_errors_stay_400_as_they_are_today(self) -> None:
        """Parity: Django's InvalidFilter → 400. Changing it would break clients."""
        assert ValidationError("min_price must be >= 0").http_status == 400

    def test_upstream_failure_stays_502_as_it_is_today(self) -> None:
        """Parity: Django's UpstreamUnavailable → 502."""
        assert UpstreamUnavailableError("WB timed out").http_status == 502


class TestGrpcMapping:
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (ValidationError("x"), GrpcStatus.INVALID_ARGUMENT),
            (UnauthenticatedError("x"), GrpcStatus.UNAUTHENTICATED),
            (PermissionDeniedError("x"), GrpcStatus.PERMISSION_DENIED),
            (NotFoundError("x"), GrpcStatus.NOT_FOUND),
            (ConflictError("x"), GrpcStatus.ALREADY_EXISTS),
            (RateLimitedError("x"), GrpcStatus.RESOURCE_EXHAUSTED),
            (InternalError("x"), GrpcStatus.INTERNAL),
            (UpstreamUnavailableError("x"), GrpcStatus.UNAVAILABLE),
        ],
    )
    def test_error_maps_to_expected_grpc_code(self, error: PlatformError, code: int) -> None:
        assert error.grpc_code == code

    def test_grpc_codes_are_the_canonical_numbers(self) -> None:
        """Fixed by the gRPC spec — a service on another stack must agree."""
        assert (GrpcStatus.OK, GrpcStatus.NOT_FOUND, GrpcStatus.INTERNAL) == (0, 5, 13)


class TestEnvelope:
    def test_shape_matches_the_documented_contract(self) -> None:
        envelope = to_envelope(NotFoundError("Product not found."), trace_id="abc123")

        assert envelope == {
            "error": {
                "code": "not_found",
                "message": "Product not found.",
                "trace_id": "abc123",
            }
        }

    def test_details_carry_field_level_information(self) -> None:
        error = ValidationError(
            "Request validation failed.",
            details=[FieldError(field="price.gte", code="out_of_range")],
        )

        envelope = to_envelope(error, trace_id="t")

        assert envelope["error"]["details"] == [{"field": "price.gte", "code": "out_of_range"}]

    def test_field_error_carries_an_optional_human_message(self) -> None:
        error = ValidationError(
            "Request validation failed.",
            details=[
                FieldError(field="rating", code="out_of_range", message="Must be within [0, 5]")
            ],
        )

        (detail,) = to_envelope(error, trace_id="t")["error"]["details"]
        assert detail["message"] == "Must be within [0, 5]"

    def test_empty_details_are_omitted_not_null(self) -> None:
        """A null field every client must skip is noise in the contract."""
        assert "details" not in to_envelope(NotFoundError("x"), trace_id="t")["error"]

    def test_envelope_emits_only_whitelisted_keys(self) -> None:
        """Structural guarantee: a new attribute cannot leak by being added."""
        error = ValidationError(
            "bad",
            details=[FieldError(field="f", code="c")],
            retry_after=5,
            context={"internal": "secret"},
        )

        assert set(to_envelope(error, trace_id="t")["error"]) == {
            "code",
            "message",
            "details",
            "retry_after",
            "trace_id",
        }

    def test_trace_id_comes_from_log_context_when_not_passed(self) -> None:
        """The handler should not have to plumb it — logging already bound it."""
        bind_context(trace_id="from-context")

        assert to_envelope(NotFoundError("x"))["error"]["trace_id"] == "from-context"

    def test_trace_id_is_omitted_when_there_is_none(self) -> None:
        assert "trace_id" not in to_envelope(NotFoundError("x"))["error"]

    def test_retry_after_is_exposed_for_throttling(self) -> None:
        envelope = to_envelope(RateLimitedError("Slow down.", retry_after=60), trace_id="t")

        assert envelope["error"]["retry_after"] == 60


class TestNoInternalLeak:
    """The DoD: internals must not reach the client under any status code."""

    def test_unexpected_exception_becomes_a_generic_500(self) -> None:
        status, envelope = envelope_from_exception(
            ZeroDivisionError("division by zero"), trace_id="t"
        )

        assert status == 500
        assert envelope["error"]["code"] == "internal_error"

    def test_unexpected_exception_message_is_not_disclosed(self) -> None:
        """`str(exc)` routinely carries SQL, file paths and connection strings."""
        secret = 'relation "catalog_product" does not exist at /srv/app/repo.py:88'

        _, envelope = envelope_from_exception(RuntimeError(secret), trace_id="t")

        rendered = str(envelope)
        assert secret not in rendered
        assert "catalog_product" not in rendered
        assert "/srv/app" not in rendered

    def test_exception_type_is_not_disclosed(self) -> None:
        _, envelope = envelope_from_exception(ZeroDivisionError("x"), trace_id="t")

        assert "ZeroDivisionError" not in str(envelope)

    def test_internal_context_is_kept_for_logging_but_never_serialised(self) -> None:
        """Diagnostics belong in the log record, not in the response body."""
        error = NotFoundError(
            "Product not found.",
            context={"sql": "SELECT * FROM product WHERE id = 1", "row_count": 0},
        )

        assert error.context["row_count"] == 0  # available to the log processor
        assert "SELECT" not in str(to_envelope(error, trace_id="t"))

    def test_platform_errors_pass_through_with_their_own_status(self) -> None:
        status, envelope = envelope_from_exception(
            UpstreamUnavailableError("Upstream Wildberries request failed."), trace_id="t"
        )

        assert status == 502
        assert envelope["error"]["message"] == "Upstream Wildberries request failed."


class TestCodes:
    def test_codes_are_stable_snake_case_identifiers(self) -> None:
        """Codes are part of the public contract — clients branch on them."""
        assert ValidationError("x").code == "validation_error"
        assert NotFoundError("x").code == "not_found"
        assert UpstreamUnavailableError("x").code == "upstream_unavailable"

    def test_every_error_class_declares_a_unique_code(self) -> None:
        subclasses = _all_subclasses(PlatformError)
        codes = [cls.code for cls in subclasses]

        assert len(codes) == len(set(codes)), f"duplicate error codes: {codes}"


def _all_subclasses(cls: type[PlatformError]) -> list[type[PlatformError]]:
    found: list[type[PlatformError]] = []
    for sub in cls.__subclasses__():
        found.append(sub)
        found += _all_subclasses(sub)
    return found

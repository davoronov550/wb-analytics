"""Error model shared by every service (T012).

One hierarchy, two transports. The same ``NotFoundError`` becomes HTTP 404 at
the edge and ``NOT_FOUND`` between services, because a client that talks to
api-gateway over REST and a service that talks to catalog over gRPC must not
learn two different vocabularies for the same failure.

**The rule this module exists to enforce:** internals never reach the client.
Not an exception message, not a module path, not a SQL fragment. An unhandled
exception becomes a fixed, contentless 500; whatever it actually said goes to
the log, correlated by ``trace_id``. Leaks of this kind happen by omission —
someone returns ``str(exc)`` because it was right there — so the safe path is
the only path this module offers.

Codes are part of the public contract: clients branch on ``error.code``, so
renaming one is a breaking change even though nothing in Python references it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, ClassVar, Final

import structlog

__all__ = [
    "ConflictError",
    "FieldError",
    "GrpcStatus",
    "InternalError",
    "NotFoundError",
    "PermissionDeniedError",
    "PlatformError",
    "RateLimitedError",
    "ServiceUnavailableError",
    "UnauthenticatedError",
    "UpstreamUnavailableError",
    "ValidationError",
    "envelope_from_exception",
    "to_envelope",
]


class GrpcStatus(IntEnum):
    """Canonical gRPC status codes.

    Declared here rather than imported from ``grpcio``: this module is a base
    dependency of all nine services, and api-gateway has no reason to carry a
    gRPC runtime. The numbers are fixed by the gRPC specification, so a service
    written in another language agrees with them.
    """

    OK = 0
    CANCELLED = 1
    UNKNOWN = 2
    INVALID_ARGUMENT = 3
    DEADLINE_EXCEEDED = 4
    NOT_FOUND = 5
    ALREADY_EXISTS = 6
    PERMISSION_DENIED = 7
    RESOURCE_EXHAUSTED = 8
    FAILED_PRECONDITION = 9
    ABORTED = 10
    OUT_OF_RANGE = 11
    UNIMPLEMENTED = 12
    INTERNAL = 13
    UNAVAILABLE = 14
    DATA_LOSS = 15
    UNAUTHENTICATED = 16


@dataclass(frozen=True, slots=True)
class FieldError:
    """One field-level validation failure, safe to expose."""

    field: str
    code: str
    message: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload = {"field": self.field, "code": self.code}
        if self.message is not None:
            payload["message"] = self.message
        return payload


class PlatformError(Exception):
    """Base for every failure the platform reports deliberately.

    ``message`` is written for the client and must stay free of internals.
    ``context`` is the opposite: diagnostic data for the log record, never
    serialised. Keeping both on one object is what stops the two from being
    conflated at the call site.
    """

    code: ClassVar[str] = "error"
    http_status: ClassVar[int] = 500
    grpc_code: ClassVar[GrpcStatus] = GrpcStatus.UNKNOWN

    def __init__(
        self,
        message: str,
        *,
        details: list[FieldError] | None = None,
        retry_after: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
        self.retry_after = retry_after
        self.context = context or {}


class ValidationError(PlatformError):
    """Malformed or out-of-range input.

    400, not 422: Django's ``InvalidFilter`` returns 400 today and the frontend
    branches on it. Parity wins over the purer code.
    """

    code = "validation_error"
    http_status = 400
    grpc_code = GrpcStatus.INVALID_ARGUMENT


class UnauthenticatedError(PlatformError):
    code = "unauthenticated"
    http_status = 401
    grpc_code = GrpcStatus.UNAUTHENTICATED


class PermissionDeniedError(PlatformError):
    code = "permission_denied"
    http_status = 403
    grpc_code = GrpcStatus.PERMISSION_DENIED


class NotFoundError(PlatformError):
    """Absent — or present but owned by somebody else.

    Owner-scoped resources answer 404 rather than 403 for a foreign id, which
    is what the current scheduling and notifications views do: 403 would
    confirm that the id exists.
    """

    code = "not_found"
    http_status = 404
    grpc_code = GrpcStatus.NOT_FOUND


class ConflictError(PlatformError):
    code = "conflict"
    http_status = 409
    grpc_code = GrpcStatus.ALREADY_EXISTS


class RateLimitedError(PlatformError):
    code = "rate_limited"
    http_status = 429
    grpc_code = GrpcStatus.RESOURCE_EXHAUSTED


class InternalError(PlatformError):
    code = "internal_error"
    http_status = 500
    grpc_code = GrpcStatus.INTERNAL


class UpstreamUnavailableError(PlatformError):
    """A marketplace or third party failed.

    502, matching today's ``UpstreamUnavailable``: the fault is upstream, not
    ours, and the distinction from 503 matters when reading dashboards.
    """

    code = "upstream_unavailable"
    http_status = 502
    grpc_code = GrpcStatus.UNAVAILABLE


class ServiceUnavailableError(PlatformError):
    """Our own dependency is down — the readiness probe should be failing too."""

    code = "service_unavailable"
    http_status = 503
    grpc_code = GrpcStatus.UNAVAILABLE


# The only message an unexpected exception is allowed to produce. Deliberately
# contentless: the trace id is how the caller and the log record are joined.
_OPAQUE_INTERNAL_MESSAGE: Final = "Internal error."


def _current_trace_id() -> str | None:
    """Read the trace id bound by the logging context, if any."""
    trace_id = structlog.contextvars.get_contextvars().get("trace_id")
    return trace_id if isinstance(trace_id, str) else None


def to_envelope(error: PlatformError, *, trace_id: str | None = None) -> dict[str, Any]:
    """Render a deliberate error as the documented response body.

    Only whitelisted fields are emitted. ``context`` is structurally incapable
    of reaching the output, which is stronger than remembering to exclude it.
    """
    body: dict[str, Any] = {"code": error.code, "message": error.message}

    if error.details:
        body["details"] = [detail.as_dict() for detail in error.details]
    if error.retry_after is not None:
        body["retry_after"] = error.retry_after

    resolved = trace_id if trace_id is not None else _current_trace_id()
    if resolved is not None:
        body["trace_id"] = resolved

    return {"error": body}


def envelope_from_exception(
    exc: BaseException, *, trace_id: str | None = None
) -> tuple[int, dict[str, Any]]:
    """Turn any exception into ``(http_status, body)``.

    The single entry point for exception handlers. Anything that is not a
    ``PlatformError`` is reported as an opaque 500 — its message, type and
    traceback stay in the log, where ``trace_id`` connects them to this
    response.
    """
    if isinstance(exc, PlatformError):
        return exc.http_status, to_envelope(exc, trace_id=trace_id)

    opaque = InternalError(_OPAQUE_INTERNAL_MESSAGE)
    return opaque.http_status, to_envelope(opaque, trace_id=trace_id)

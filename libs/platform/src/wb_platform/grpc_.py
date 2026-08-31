"""gRPC glue shared by every service (T019).

Named ``grpc_`` so it cannot shadow the ``grpc`` package on the import path.

What it does is make an internal call behave like an external one. The same
``NotFoundError`` that becomes HTTP 404 at the gateway becomes ``NOT_FOUND``
between services, the trace continues across the hop, and a domain failure
never arrives as ``UNKNOWN`` with a Python traceback in the message.

That last part is the reason the error interceptor exists. gRPC's default for
an unhandled exception is ``UNKNOWN`` plus ``str(exc)`` — so a SQL fragment or a
DSN travels to the caller, and every distinct failure looks identical to the
code that has to branch on it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Final, Protocol

from wb_platform.errors import GrpcStatus, PlatformError, envelope_from_exception
from wb_platform.logging import bind_context, clear_context, get_logger
from wb_platform.otel import (
    current_trace_id,
    extract_from_grpc_metadata,
    inject_into_grpc_metadata,
    traced,
)

__all__ = [
    "GrpcError",
    "call_with_context",
    "serve_with_context",
    "to_grpc_error",
]

_TRACE_ID_METADATA: Final = "x-trace-id"

logger = get_logger(__name__)


class GrpcError(Exception):
    """A failure rendered for the wire: a status code and a safe message.

    Carries the same envelope the REST edge returns, so a caller that already
    parses ``{"error": {...}}`` needs no second format.
    """

    def __init__(self, code: GrpcStatus, message: str, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def to_grpc_error(exc: BaseException) -> GrpcError:
    """Map any exception onto a gRPC status.

    Anything that is not a :class:`PlatformError` becomes ``INTERNAL`` with a
    fixed message — the same opaque 500 the HTTP edge produces, for the same
    reason: ``str(exc)`` routinely carries SQL, file paths and connection
    strings.
    """
    _, envelope = envelope_from_exception(exc, trace_id=current_trace_id())
    body = envelope["error"]

    code = exc.grpc_code if isinstance(exc, PlatformError) else GrpcStatus.INTERNAL
    return GrpcError(code=code, message=str(body["message"]), details=envelope)


async def serve_with_context(
    handler: Callable[[], Awaitable[Any]],
    *,
    method: str,
    metadata: Sequence[tuple[str, str]] | None,
) -> Any:
    """Run a server-side handler inside the caller's trace and log context.

    Wraps rather than decorates so it works with generated stubs, which a
    decorator cannot reach without code generation of our own.

    Domain failures are re-raised as :class:`GrpcError`; the transport layer
    turns that into ``set_code``/``set_details``. Keeping the translation here
    rather than in each servicer is what stops nine services from inventing
    nine mappings.
    """
    parent = extract_from_grpc_metadata(metadata)

    with traced(method, parent=parent, attributes={"rpc.method": method}):
        bind_context(rpc_method=method)
        try:
            return await handler()
        except PlatformError as exc:
            # Expected: a domain outcome, logged at info because it is not a
            # fault of this service.
            logger.info(
                "gRPC call rejected", method=method, code=exc.code, status=exc.grpc_code.name
            )
            raise to_grpc_error(exc) from exc
        except Exception as exc:
            logger.exception("gRPC handler failed", method=method)
            raise to_grpc_error(exc) from exc
        finally:
            clear_context()


async def call_with_context(
    call: Callable[[Sequence[tuple[str, str]]], Awaitable[Any]],
    *,
    method: str,
    metadata: Sequence[tuple[str, str]] | None = None,
) -> Any:
    """Make a client-side call with the trace context attached.

    ``call`` receives the metadata to send. Passing it in rather than mutating
    a shared list keeps one client usable from concurrent tasks.
    """
    with traced(method, attributes={"rpc.method": method}):
        enriched = inject_into_grpc_metadata(list(metadata or []))
        trace_id = current_trace_id()
        if trace_id is not None:
            # Redundant with `traceparent` for machines, but it is what an
            # operator greps for when reading logs beside a failing call.
            enriched.append((_TRACE_ID_METADATA, trace_id))
        return await call(enriched)


class HealthServicer(Protocol):
    """The gRPC health-checking protocol, as Kubernetes probes expect it."""

    async def check(self) -> bool: ...

"""Tests for the gRPC glue (T019).

The contract under test: a domain error reaches a gRPC caller with the same
meaning it would have over REST.

Without this, gRPC's default takes over — every unhandled exception becomes
``UNKNOWN`` carrying ``str(exc)``. That is two failures at once: the caller
cannot tell "not found" from "database down", and the message it receives
routinely contains SQL, a file path or a DSN.
"""

from __future__ import annotations

from typing import Any

import pytest

from wb_platform.config import Environment, LogLevel, ObservabilitySettings, ServiceSettings
from wb_platform.errors import (
    ConflictError,
    GrpcStatus,
    NotFoundError,
    UpstreamUnavailableError,
    ValidationError,
)
from wb_platform.grpc_ import GrpcError, call_with_context, serve_with_context, to_grpc_error
from wb_platform.otel import configure_tracing, current_trace_id, shutdown_tracing, traced


@pytest.fixture(autouse=True)
def tracing() -> Any:
    configure_tracing(
        ServiceSettings(
            service_name="catalog", environment=Environment.PRODUCTION, log_level=LogLevel.INFO
        ),
        ObservabilitySettings(),
    )
    yield
    shutdown_tracing()


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (ValidationError("bad"), GrpcStatus.INVALID_ARGUMENT),
            (NotFoundError("gone"), GrpcStatus.NOT_FOUND),
            (ConflictError("dup"), GrpcStatus.ALREADY_EXISTS),
            (UpstreamUnavailableError("wb down"), GrpcStatus.UNAVAILABLE),
        ],
    )
    def test_domain_errors_keep_their_meaning(self, error: Exception, code: GrpcStatus) -> None:
        """The same error is 404 over REST and NOT_FOUND here — one vocabulary."""
        assert to_grpc_error(error).code == code

    def test_unexpected_exception_becomes_internal(self) -> None:
        assert to_grpc_error(ZeroDivisionError("x")).code == GrpcStatus.INTERNAL

    def test_unexpected_exception_message_is_not_disclosed(self) -> None:
        """gRPC's default would put this straight on the wire."""
        secret = 'relation "catalog_product" does not exist at /srv/app/repo.py:88'

        rendered = to_grpc_error(RuntimeError(secret))

        assert secret not in rendered.message
        assert "catalog_product" not in str(rendered.details)

    def test_domain_message_is_preserved(self) -> None:
        """Deliberate messages are safe by construction and useful to the caller."""
        assert to_grpc_error(NotFoundError("Product not found.")).message == "Product not found."

    def test_details_carry_the_same_envelope_as_rest(self) -> None:
        """A caller that already parses {"error": {...}} needs no second format."""
        details = to_grpc_error(NotFoundError("gone")).details

        assert set(details) == {"error"}
        assert details["error"]["code"] == "not_found"


class TestServer:
    @pytest.mark.asyncio
    async def test_successful_handler_returns_its_value(self) -> None:
        async def handler() -> str:
            return "ok"

        result = await serve_with_context(handler, method="catalog.List", metadata=None)

        assert result == "ok"

    @pytest.mark.asyncio
    async def test_domain_error_arrives_as_a_grpc_error(self) -> None:
        async def handler() -> None:
            raise NotFoundError("Product not found.")

        with pytest.raises(GrpcError) as exc:
            await serve_with_context(handler, method="catalog.Get", metadata=None)

        assert exc.value.code == GrpcStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_unexpected_error_arrives_opaque(self) -> None:
        async def handler() -> None:
            raise ZeroDivisionError("division by zero at repo.py:12")

        with pytest.raises(GrpcError) as exc:
            await serve_with_context(handler, method="catalog.Get", metadata=None)

        assert exc.value.code == GrpcStatus.INTERNAL
        assert "repo.py" not in exc.value.message


class TestTracePropagation:
    @pytest.mark.asyncio
    async def test_server_continues_the_client_trace(self) -> None:
        sent: list[tuple[str, str]] = []

        async def transport(metadata: Any) -> str:
            sent.extend(metadata)
            return "sent"

        with traced("outer"):
            expected = current_trace_id()
            await call_with_context(transport, method="catalog.List")

        seen: list[str | None] = []

        async def handler() -> None:
            seen.append(current_trace_id())

        await serve_with_context(handler, method="catalog.List", metadata=sent)

        assert seen == [expected]

    @pytest.mark.asyncio
    async def test_client_sends_a_greppable_trace_id_too(self) -> None:
        """`traceparent` is for machines; this is what an operator greps for."""
        sent: list[tuple[str, str]] = []

        async def transport(metadata: Any) -> None:
            sent.extend(metadata)

        with traced("outer"):
            expected = current_trace_id()
            await call_with_context(transport, method="catalog.List")

        assert dict(sent)["x-trace-id"] == expected

    @pytest.mark.asyncio
    async def test_caller_metadata_is_preserved(self) -> None:
        sent: list[tuple[str, str]] = []

        async def transport(metadata: Any) -> None:
            sent.extend(metadata)

        await call_with_context(
            transport, method="catalog.List", metadata=[("authorization", "Bearer x")]
        )

        assert dict(sent)["authorization"] == "Bearer x"

    @pytest.mark.asyncio
    async def test_call_without_a_trace_still_works(self) -> None:
        """A CLI or a cron job has no incoming trace to continue."""
        sent: list[tuple[str, str]] = []

        async def transport(metadata: Any) -> str:
            sent.extend(metadata)
            return "ok"

        assert await call_with_context(transport, method="catalog.List") == "ok"

    @pytest.mark.asyncio
    async def test_server_without_metadata_starts_a_new_trace(self) -> None:
        seen: list[str | None] = []

        async def handler() -> None:
            seen.append(current_trace_id())

        await serve_with_context(handler, method="catalog.List", metadata=None)

        assert seen[0] is not None

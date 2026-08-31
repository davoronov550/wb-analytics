"""Tests for structured logging (T011).

The contract under test: every record — ours or a third-party library's —
comes out as one JSON line carrying the service name and whatever request
context is bound, without any call site passing those fields explicitly.

That "without passing" part is the whole point. Threading a trace id through
every function signature is what teams actually fail to do, and the first
missing hop is the one that matters during an incident.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Iterator

import pytest
from pydantic import PostgresDsn, TypeAdapter

from wb_platform.config import Environment, LogLevel, ServiceSettings
from wb_platform.logging import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    log_context,
)


def _settings(
    name: str = "catalog",
    env: Environment = Environment.PRODUCTION,
    level: LogLevel = LogLevel.INFO,
) -> ServiceSettings:
    return ServiceSettings(service_name=name, environment=env, log_level=level)


@pytest.fixture
def stream() -> Iterator[io.StringIO]:
    """A configured logging pipeline writing JSON into an in-memory buffer."""
    buffer = io.StringIO()
    configure_logging(_settings(), stream=buffer)
    yield buffer
    clear_context()
    logging.getLogger().handlers.clear()


def records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


class TestServiceIdentity:
    def test_service_name_is_present_without_being_passed(self, stream: io.StringIO) -> None:
        get_logger().info("collection finished")

        (record,) = records(stream)
        assert record["service"] == "catalog"
        assert record["event"] == "collection finished"

    def test_every_record_carries_level_and_timestamp(self, stream: io.StringIO) -> None:
        get_logger().warning("upstream slow")

        (record,) = records(stream)
        assert record["level"] == "warning"
        # ISO-8601 in UTC — sortable as text, unambiguous across regions.
        assert str(record["timestamp"]).endswith("Z")


class TestRequestContext:
    def test_bound_context_reaches_records_without_being_passed(self, stream: io.StringIO) -> None:
        bind_context(trace_id="4bf92f3577b34da6", owner_id=42)

        get_logger().info("products listed")

        (record,) = records(stream)
        assert record["trace_id"] == "4bf92f3577b34da6"
        assert record["owner_id"] == 42

    def test_absent_context_does_not_invent_fields(self, stream: io.StringIO) -> None:
        get_logger().info("no request in flight")

        (record,) = records(stream)
        assert "trace_id" not in record

    def test_clear_context_removes_bound_fields(self, stream: io.StringIO) -> None:
        bind_context(trace_id="abc")
        clear_context()

        get_logger().info("after clear")

        (record,) = records(stream)
        assert "trace_id" not in record

    def test_log_context_scopes_fields_to_the_block(self, stream: io.StringIO) -> None:
        with log_context(query="наушники"):
            get_logger().info("inside")
        get_logger().info("outside")

        inside, outside = records(stream)
        assert inside["query"] == "наушники"
        assert "query" not in outside

    def test_log_context_restores_previous_value_on_exit(self, stream: io.StringIO) -> None:
        bind_context(trace_id="outer")
        with log_context(trace_id="inner"):
            get_logger().info("nested")
        get_logger().info("restored")

        nested, restored = records(stream)
        assert nested["trace_id"] == "inner"
        assert restored["trace_id"] == "outer"

    @pytest.mark.asyncio
    async def test_concurrent_tasks_do_not_share_context(self, stream: io.StringIO) -> None:
        """Two in-flight requests must never borrow each other's trace id.

        This is the property that makes contextvars the right tool and a module
        global the wrong one; with nine services and async handlers everywhere,
        cross-request bleed would be both silent and untraceable.
        """

        async def handle(trace_id: str) -> None:
            bind_context(trace_id=trace_id)
            await asyncio.sleep(0)  # force interleaving
            get_logger().info("handled")

        await asyncio.gather(handle("aaa"), handle("bbb"))

        seen = {str(r["trace_id"]) for r in records(stream)}
        assert seen == {"aaa", "bbb"}


class TestThirdPartyLibraries:
    def test_stdlib_records_go_through_the_same_pipeline(self, stream: io.StringIO) -> None:
        """aiokafka, SQLAlchemy and uvicorn log through stdlib, not structlog.

        If their records bypass the pipeline, half the production output is
        unparseable and carries no correlation id — which is exactly the half
        you need when the broker misbehaves.
        """
        bind_context(trace_id="shared")

        logging.getLogger("aiokafka.consumer").warning("group rebalancing")

        (record,) = records(stream)
        assert record["service"] == "catalog"
        assert record["trace_id"] == "shared"
        assert record["logger"] == "aiokafka.consumer"
        assert record["event"] == "group rebalancing"


class TestSecretRedaction:
    def test_sensitive_keys_are_redacted(self, stream: io.StringIO) -> None:
        get_logger().info("auth attempt", password="hunter2", authorization="Bearer xyz")

        (record,) = records(stream)
        assert record["password"] == "***"
        assert record["authorization"] == "***"

    def test_credentials_inside_urls_are_redacted(self, stream: io.StringIO) -> None:
        get_logger().info("connecting", dsn="postgresql+asyncpg://wb_app:wbapp@db:5432/catalog")

        (record,) = records(stream)
        assert "wbapp" not in str(record["dsn"])
        assert "wb_app" in str(record["dsn"])  # user is diagnostic, password is not

    def test_redaction_reaches_nested_values(self, stream: io.StringIO) -> None:
        get_logger().info("upstream call", headers={"Authorization": "Bearer xyz"})

        (record,) = records(stream)
        assert record["headers"] == {"Authorization": "***"}

    def test_dsn_objects_do_not_leak_their_password(self, stream: io.StringIO) -> None:
        """A Pydantic DSN is an object, not a string — and its repr holds the password.

        Redaction runs before serialization, so a str-only rule lets the
        renderer print the credential itself. This leaked until the processor
        learned to inspect the text form of opaque objects.
        """
        dsn = TypeAdapter(PostgresDsn).validate_python(
            "postgresql+asyncpg://wb_app:hunter2@db:5432/catalog"
        )

        get_logger().info("connecting", dsn=dsn)

        (record,) = records(stream)
        assert "hunter2" not in str(record["dsn"])
        assert "wb_app" in str(record["dsn"])

    def test_numbers_survive_redaction_untouched(self, stream: io.StringIO) -> None:
        """Guards the fast path: scalars must not be stringified on the way out."""
        get_logger().info("collection finished", created=42, ratio=0.5, ok=True)

        (record,) = records(stream)
        assert record["created"] == 42
        assert record["ratio"] == 0.5
        assert record["ok"] is True


class TestExceptions:
    def test_exception_is_rendered_as_structured_data(self, stream: io.StringIO) -> None:
        try:
            raise ValueError("upstream Wildberries failure")
        except ValueError:
            get_logger().exception("collection failed")

        (record,) = records(stream)
        assert record["level"] == "error"
        assert "ValueError" in json.dumps(record["exception"], ensure_ascii=False)


class TestLevels:
    def test_records_below_configured_level_are_dropped(self) -> None:
        buffer = io.StringIO()
        configure_logging(_settings(level=LogLevel.WARNING), stream=buffer)

        get_logger().info("chatty")
        get_logger().error("real problem")

        assert [r["event"] for r in records(buffer)] == ["real problem"]
        logging.getLogger().handlers.clear()


class TestRenderer:
    def test_local_environment_uses_human_readable_output(self) -> None:
        """JSON is for machines; a developer reading a terminal is not one."""
        buffer = io.StringIO()
        configure_logging(_settings(env=Environment.LOCAL), stream=buffer)

        get_logger().info("collection finished", count=42)

        output = buffer.getvalue()
        assert "collection finished" in output
        with pytest.raises(json.JSONDecodeError):
            json.loads(output.splitlines()[0])
        logging.getLogger().handlers.clear()

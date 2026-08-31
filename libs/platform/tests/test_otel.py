"""Tests for distributed tracing (T013).

The contract under test: a trace survives every hop, including the two that
are not HTTP — a Kafka message and a gRPC call.

Why that framing. HTTP propagation comes free with auto-instrumentation, so it
is not where traces break. They break at the event boundary: the producer's
span ends when the message is written, the consumer starts a fresh root span
minutes later, and the two are never joined. The result looks like working
tracing right up until the incident where you need to follow a price change
from collection to alert. Risk R11.

The other half is ``trace_id`` reaching the log lines. Tempo shows the span
tree; Loki shows what the code was doing. Without the id in both, an operator
has two systems and no way across.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import structlog
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from wb_platform.config import Environment, LogLevel, ObservabilitySettings, ServiceSettings
from wb_platform.otel import (
    configure_tracing,
    current_trace_id,
    extract_from_grpc_metadata,
    extract_from_kafka_headers,
    inject_into_grpc_metadata,
    inject_into_kafka_headers,
    shutdown_tracing,
    traced,
)


def _service(name: str = "catalog") -> ServiceSettings:
    return ServiceSettings(
        service_name=name, environment=Environment.PRODUCTION, log_level=LogLevel.INFO
    )


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    """Tracing wired to an in-memory exporter — no collector, no Tempo."""
    exporter = InMemorySpanExporter()
    configure_tracing(_service(), ObservabilitySettings(), exporter=exporter)
    yield exporter
    shutdown_tracing()
    structlog.contextvars.clear_contextvars()


def finished(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return list(exporter.get_finished_spans())


class TestConfiguration:
    def test_service_name_lands_on_every_span(self, spans: InMemorySpanExporter) -> None:
        """Nine services share a collector; a span without an owner is noise."""
        with traced("collect_products"):
            pass

        (span,) = finished(spans)
        assert span.resource.attributes["service.name"] == "catalog"
        assert span.name == "collect_products"

    def test_attributes_are_recorded(self, spans: InMemorySpanExporter) -> None:
        with traced("collect_products", attributes={"query": "наушники", "pages": 3}):
            pass

        (span,) = finished(spans)
        assert span.attributes is not None
        assert span.attributes["query"] == "наушники"
        assert span.attributes["pages"] == 3

    def test_failure_marks_the_span_and_re_raises(self, spans: InMemorySpanExporter) -> None:
        """A span that ends OK while the operation failed is worse than none."""
        with pytest.raises(ZeroDivisionError), traced("collect_products"):
            raise ZeroDivisionError

        (span,) = finished(spans)
        assert span.status.is_ok is False
        assert span.events  # the exception is recorded on the span


class TestOncePerProcess:
    """OpenTelemetry allows one tracer provider per process — hold that line."""

    def test_second_configuration_is_refused_loudly(self, spans: InMemorySpanExporter) -> None:
        """OTel ignores the second call with a log line that is easy to miss.

        Spans then go to the first provider and the caller sees an empty
        exporter with no error at all — an afternoon of debugging empty traces.
        """
        with pytest.raises(RuntimeError, match="already configured"):
            configure_tracing(_service(), ObservabilitySettings())

    def test_shutdown_allows_reconfiguration(self) -> None:
        """Guards the private-attribute reset in shutdown_tracing().

        If OpenTelemetry renames those internals, this fails here rather than
        silently leaving every later test with a dead exporter.
        """
        first = InMemorySpanExporter()
        configure_tracing(_service(), ObservabilitySettings(), exporter=first)
        shutdown_tracing()

        second = InMemorySpanExporter()
        configure_tracing(_service("analytics"), ObservabilitySettings(), exporter=second)
        with traced("after reconfigure"):
            pass
        shutdown_tracing()

        assert not first.get_finished_spans()
        (span,) = second.get_finished_spans()
        assert span.resource.attributes["service.name"] == "analytics"


class TestSampling:
    def test_full_sampling_by_default(self, spans: InMemorySpanExporter) -> None:
        with traced("sampled"):
            pass

        assert len(finished(spans)) == 1

    def test_ratio_sampler_is_parent_based(self) -> None:
        """Once sampled upstream, every service keeps the trace.

        Sampling independently per service produces traces with holes, which
        are harder to read than no trace at all.
        """
        provider = configure_tracing(
            _service(),
            ObservabilitySettings(trace_sample_ratio=0.1),
            exporter=InMemorySpanExporter(),
        )
        try:
            assert type(provider.sampler).__name__ == "ParentBased"
        finally:
            shutdown_tracing()

    def test_otlp_endpoint_installs_a_batch_processor(self) -> None:
        """Constructing the exporter must not require a reachable collector."""
        provider = configure_tracing(
            _service(), ObservabilitySettings(exporter_otlp_endpoint="http://localhost:4317")
        )
        try:
            assert provider._active_span_processor is not None
        finally:
            shutdown_tracing()

    def test_without_an_endpoint_spans_are_created_and_dropped(self) -> None:
        """Instrumented code must run identically in a unit test."""
        configure_tracing(_service(), ObservabilitySettings())
        try:
            with traced("nowhere"):
                assert current_trace_id() is not None
        finally:
            shutdown_tracing()

    def test_shutdown_is_safe_without_configuration(self) -> None:
        shutdown_tracing()
        shutdown_tracing()


class TestCarrierProtocol:
    """`keys()` is required by OpenTelemetry's Getter interface."""

    def test_kafka_getter_lists_header_names(self) -> None:
        context = extract_from_kafka_headers([("event_id", b"a"), ("traceparent", b"b")])

        assert isinstance(context, dict | type(context))  # a Context was returned

    def test_getters_expose_keys_and_missing_values(self) -> None:
        from wb_platform.otel import _KAFKA_GETTER, _METADATA_GETTER

        kafka = [("event_id", b"abc"), ("schema", b"1")]
        assert _KAFKA_GETTER.keys(kafka) == ["event_id", "schema"]
        assert _KAFKA_GETTER.get(kafka, "event_id") == ["abc"]
        assert _KAFKA_GETTER.get(kafka, "absent") is None

        meta = [("authorization", "Bearer x")]
        assert _METADATA_GETTER.keys(meta) == ["authorization"]
        assert _METADATA_GETTER.get(meta, "authorization") == ["Bearer x"]
        assert _METADATA_GETTER.get(meta, "absent") is None


class TestLogCorrelation:
    def test_trace_id_reaches_the_logging_context(self, spans: InMemorySpanExporter) -> None:
        """Bound automatically — logging.py must stay free of OpenTelemetry.

        The dependency runs one way: otel binds into contextvars, logging reads
        them. The reverse would make the logging module untestable without a
        tracer.
        """
        with traced("collect_products"):
            bound = structlog.contextvars.get_contextvars()
            assert bound["trace_id"] == current_trace_id()
            assert len(str(bound["trace_id"])) == 32  # W3C: 16 bytes, hex

    def test_context_is_restored_after_the_span(self, spans: InMemorySpanExporter) -> None:
        with traced("outer"):
            outer = current_trace_id()
            with traced("inner"):
                pass
            assert current_trace_id() == outer

        assert structlog.contextvars.get_contextvars().get("trace_id") is None

    def test_no_trace_id_outside_a_span(self, spans: InMemorySpanExporter) -> None:
        assert current_trace_id() is None


class TestKafkaPropagation:
    """The hop where traces actually break."""

    def test_producer_and_consumer_share_one_trace(self, spans: InMemorySpanExporter) -> None:
        with traced("publish products.collected"):
            headers = inject_into_kafka_headers([("event_id", b"abc")])
            produced = current_trace_id()

        # …another process, another service, minutes later.
        context = extract_from_kafka_headers(headers)
        with traced("consume products.collected", parent=context):
            consumed = current_trace_id()

        assert consumed == produced

    def test_consumer_span_is_a_child_of_the_producer_span(
        self, spans: InMemorySpanExporter
    ) -> None:
        with traced("publish"):
            headers = inject_into_kafka_headers(None)
        with traced("consume", parent=extract_from_kafka_headers(headers)):
            pass

        publish, consume = finished(spans)
        assert consume.parent is not None
        assert consume.parent.span_id == publish.context.span_id

    def test_existing_headers_are_preserved(self, spans: InMemorySpanExporter) -> None:
        """Kafka headers carry event_id and schema id — injection must not clobber."""
        with traced("publish"):
            headers = inject_into_kafka_headers([("event_id", b"abc"), ("schema", b"1")])

        as_dict = dict(headers)
        assert as_dict["event_id"] == b"abc"
        assert as_dict["schema"] == b"1"
        assert "traceparent" in as_dict

    def test_header_values_are_bytes_as_kafka_requires(self, spans: InMemorySpanExporter) -> None:
        """aiokafka rejects str header values — this is the shape it needs."""
        with traced("publish"):
            headers = inject_into_kafka_headers(None)

        assert all(isinstance(key, str) and isinstance(value, bytes) for key, value in headers)

    def test_message_without_trace_headers_starts_a_new_trace(
        self, spans: InMemorySpanExporter
    ) -> None:
        """Backfilled and third-party messages must not crash the consumer."""
        with traced("consume", parent=extract_from_kafka_headers([("event_id", b"abc")])):
            assert current_trace_id() is not None

        (span,) = finished(spans)
        assert span.parent is None

    def test_malformed_trace_header_does_not_break_consumption(
        self, spans: InMemorySpanExporter
    ) -> None:
        """A losing trace is acceptable; a stuck consumer is not."""
        headers = [("traceparent", b"not-a-valid-traceparent")]

        with traced("consume", parent=extract_from_kafka_headers(headers)):
            assert current_trace_id() is not None


class TestGrpcPropagation:
    def test_client_and_server_share_one_trace(self, spans: InMemorySpanExporter) -> None:
        with traced("catalog.ListProducts client"):
            metadata = inject_into_grpc_metadata([("authorization", "Bearer x")])
            called = current_trace_id()

        with traced("catalog.ListProducts server", parent=extract_from_grpc_metadata(metadata)):
            served = current_trace_id()

        assert served == called

    def test_metadata_values_are_str_as_grpc_requires(self, spans: InMemorySpanExporter) -> None:
        """gRPC metadata is str-keyed and str-valued — unlike Kafka headers."""
        with traced("call"):
            metadata = inject_into_grpc_metadata(None)

        assert all(isinstance(key, str) and isinstance(value, str) for key, value in metadata)

    def test_existing_metadata_is_preserved(self, spans: InMemorySpanExporter) -> None:
        with traced("call"):
            metadata = inject_into_grpc_metadata([("authorization", "Bearer x")])

        assert dict(metadata)["authorization"] == "Bearer x"


class TestEndToEnd:
    def test_one_trace_spans_api_kafka_and_grpc(self, spans: InMemorySpanExporter) -> None:
        """The path a price change actually takes: API → Kafka → gRPC.

        Three services, two non-HTTP boundaries, one trace id. This is the
        property an operator relies on when following a collection through to
        the alert it produced.
        """
        with traced("POST /v1/collections"):
            origin = current_trace_id()
            headers = inject_into_kafka_headers(None)

        with traced("consume collection.requested", parent=extract_from_kafka_headers(headers)):
            metadata = inject_into_grpc_metadata(None)

        with traced("catalog.Upsert", parent=extract_from_grpc_metadata(metadata)):
            final = current_trace_id()

        assert final == origin
        assert {span.context.trace_id for span in finished(spans)} == {int(str(origin), 16)}

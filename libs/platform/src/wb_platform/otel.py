"""Distributed tracing shared by every service (T013).

HTTP propagation comes free with auto-instrumentation, so it is not where
traces break. They break at the two boundaries nothing instruments for you:

* **Kafka.** The producer's span ends when the message is written; the consumer
  starts a fresh root span minutes later, and nothing joins them. Tracing looks
  healthy right up to the incident where you need to follow a price change from
  collection through to the alert it produced.
* **gRPC metadata.** Same shape, different carrier — and a different value type,
  which is the reason for two nearly identical pairs of functions below rather
  than one generic pair with a mode flag.

The second job of this module is putting ``trace_id`` into the logging context.
Tempo shows the span tree, Loki shows what the code was doing; without the id in
both, an operator has two systems and no way across. The dependency runs one
way — otel binds into contextvars, ``logging`` reads them — so the logging
module stays testable without a tracer.

Risk R11 in [док. 6](../../../../docs/migration/06-risks.md).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Final

import structlog
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.propagators.textmap import Getter, Setter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased, TraceIdRatioBased
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from wb_platform.config import ObservabilitySettings, ServiceSettings

__all__ = [
    "configure_tracing",
    "current_trace_id",
    "extract_from_grpc_metadata",
    "extract_from_kafka_headers",
    "inject_into_grpc_metadata",
    "inject_into_kafka_headers",
    "shutdown_tracing",
    "traced",
]

# W3C trace context. Chosen over B3 because it is what OpenTelemetry, Traefik
# and every managed collector speak by default — the fewer translation points,
# the fewer places a trace can be dropped.
_PROPAGATOR: Final = TraceContextTextMapPropagator()

_KAFKA_HEADER_ENCODING: Final = "utf-8"

_provider: TracerProvider | None = None


# --------------------------------------------------------------------------
# Carriers
# --------------------------------------------------------------------------

# Kafka headers are `list[tuple[str, bytes]]`; gRPC metadata is
# `list[tuple[str, str]]`. Two carrier shapes, so two setter/getter pairs. A
# single generic pair with a "bytes or str" switch would be shorter and would
# put a runtime type check on the hot path of every message.


class _KafkaSetter(Setter[list[tuple[str, bytes]]]):
    def set(self, carrier: list[tuple[str, bytes]], key: str, value: str) -> None:
        carrier.append((key, value.encode(_KAFKA_HEADER_ENCODING)))


class _KafkaGetter(Getter[Sequence[tuple[str, bytes]]]):
    def get(self, carrier: Sequence[tuple[str, bytes]], key: str) -> list[str] | None:
        values = [
            value.decode(_KAFKA_HEADER_ENCODING, errors="replace")
            for header, value in carrier
            if header == key
        ]
        return values or None

    def keys(self, carrier: Sequence[tuple[str, bytes]]) -> list[str]:
        return [header for header, _ in carrier]


class _MetadataSetter(Setter[list[tuple[str, str]]]):
    def set(self, carrier: list[tuple[str, str]], key: str, value: str) -> None:
        carrier.append((key, value))


class _MetadataGetter(Getter[Sequence[tuple[str, str]]]):
    def get(self, carrier: Sequence[tuple[str, str]], key: str) -> list[str] | None:
        values = [value for header, value in carrier if header == key]
        return values or None

    def keys(self, carrier: Sequence[tuple[str, str]]) -> list[str]:
        return [header for header, _ in carrier]


_KAFKA_SETTER: Final = _KafkaSetter()
_KAFKA_GETTER: Final = _KafkaGetter()
_METADATA_SETTER: Final = _MetadataSetter()
_METADATA_GETTER: Final = _MetadataGetter()


def inject_into_kafka_headers(
    headers: Sequence[tuple[str, bytes]] | None,
) -> list[tuple[str, bytes]]:
    """Add ``traceparent`` to Kafka headers, preserving what is already there.

    Returns a new list: mutating the caller's headers would surprise a producer
    that reuses one header list across messages.
    """
    carrier: list[tuple[str, bytes]] = list(headers or [])
    _PROPAGATOR.inject(carrier, setter=_KAFKA_SETTER)
    return carrier


def extract_from_kafka_headers(headers: Sequence[tuple[str, bytes]] | None) -> Context:
    """Recover the producer's context from Kafka headers.

    Missing or malformed headers yield an empty context rather than an error:
    backfilled and third-party messages must not stall a consumer. Losing one
    trace is acceptable; a stuck consumer is not.
    """
    return _PROPAGATOR.extract(list(headers or []), getter=_KAFKA_GETTER)


def inject_into_grpc_metadata(
    metadata: Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    """Add ``traceparent`` to gRPC metadata, preserving what is already there."""
    carrier: list[tuple[str, str]] = list(metadata or [])
    _PROPAGATOR.inject(carrier, setter=_METADATA_SETTER)
    return carrier


def extract_from_grpc_metadata(metadata: Sequence[tuple[str, str]] | None) -> Context:
    """Recover the caller's context from gRPC metadata."""
    return _PROPAGATOR.extract(list(metadata or []), getter=_METADATA_GETTER)


# --------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------


def configure_tracing(
    service: ServiceSettings,
    observability: ObservabilitySettings,
    *,
    exporter: SpanExporter | None = None,
) -> TracerProvider:
    """Install the tracer provider. Call **once**, from the composition root.

    ``exporter`` is for tests — an in-memory one makes the propagation
    behaviour assertable without a collector. In production the OTLP endpoint
    comes from settings; with no endpoint configured, spans are created and
    dropped, so instrumented code runs identically in a unit test.

    Once per process is OpenTelemetry's own constraint, not ours: a second
    ``set_tracer_provider`` is ignored with a log line that is easy to miss,
    after which spans go to the first provider and the caller sees an empty
    exporter with no error. Refusing loudly is the difference between a failed
    call and an afternoon of debugging empty traces.
    """
    global _provider

    if _provider is not None:
        raise RuntimeError(
            "Tracing is already configured. OpenTelemetry allows one tracer "
            "provider per process; call configure_tracing once from the "
            "composition root, and shutdown_tracing() before reconfiguring."
        )

    provider = TracerProvider(
        resource=Resource.create({"service.name": service.service_name}),
        # ParentBased: once a trace is sampled upstream, every service keeps
        # it. Sampling per service independently would produce traces with
        # holes, which are harder to read than no trace at all.
        sampler=ParentBased(
            ALWAYS_ON
            if observability.trace_sample_ratio >= 1.0
            else TraceIdRatioBased(observability.trace_sample_ratio)
        ),
    )

    processor = _span_processor(exporter, observability)
    if processor is not None:
        provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def _span_processor(
    exporter: SpanExporter | None, observability: ObservabilitySettings
) -> SpanProcessor | None:
    if exporter is not None:
        # Simple, not batched: a test must see the span the moment it ends.
        return SimpleSpanProcessor(exporter)
    if observability.exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        return BatchSpanProcessor(OTLPSpanExporter(endpoint=observability.exporter_otlp_endpoint))
    return None


def shutdown_tracing() -> None:
    """Flush and release the provider — for tests and graceful shutdown.

    Resets OpenTelemetry's global so a later ``configure_tracing`` succeeds.
    The global has no public setter for this, hence the private attribute:
    the alternative is a process that can never reconfigure tracing, which
    makes the module untestable.
    """
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


# --------------------------------------------------------------------------
# Spans
# --------------------------------------------------------------------------


def current_trace_id() -> str | None:
    """The active trace id as 32 hex characters, or ``None`` outside a span."""
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return None
    return format(context.trace_id, "032x")


@contextmanager
def traced(
    name: str,
    *,
    parent: Context | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Run a block inside a span, with ``trace_id`` bound to the log context.

    ``parent`` accepts the context returned by the ``extract_*`` functions,
    which is how a consumer or gRPC handler continues an existing trace instead
    of starting a new one.

    A failing block marks the span as errored and re-raises: a span that ends
    OK while the operation failed is worse than no span, because it is believed.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        name, context=parent, kind=kind, attributes=dict(attributes or {})
    ) as span:
        tokens = structlog.contextvars.bind_contextvars(trace_id=current_trace_id())
        try:
            yield span
        except BaseException as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise
        finally:
            structlog.contextvars.reset_contextvars(**tokens)

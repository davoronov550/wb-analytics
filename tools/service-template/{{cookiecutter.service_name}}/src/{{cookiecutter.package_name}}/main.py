"""ASGI entry point for the {{ cookiecutter.service_name }} service.

The only place that knows about FastAPI. Everything below `adapters/` is
wired here and nowhere else, so the composition root stays the single answer
to "where does this dependency come from".

What this file exists to get right, once, for all nine services:

* logging and tracing configured **before** anything else runs, so a failure
  during startup is still structured and still carries a trace id;
* one exception handler, so no route can answer with an unenveloped error or
  leak an internal message;
* ``/healthz`` and ``/readyz`` kept distinct — the first must never touch a
  dependency, because Kubernetes *restarts* what fails it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from {{ cookiecutter.package_name }}.composition.container import Container
from wb_platform.config import ObservabilitySettings, ServiceSettings
from wb_platform.errors import envelope_from_exception
from wb_platform.health import HealthRegistry, liveness, require_ready
from wb_platform.logging import configure_logging, get_logger
from wb_platform.otel import configure_tracing, current_trace_id, shutdown_tracing

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build dependencies on startup, release them on shutdown.

    Failing here is the intended behaviour for bad configuration: a service
    that starts with half its dependencies missing fails later, further from
    the cause, and usually in front of a user.
    """
    container: Container = app.state.container
    await container.start()
    # Registered after start so a check cannot run against a half-built
    # dependency, and here rather than in create_app so /readyz always
    # reflects what the container actually opened.
    container.register_health_checks(app.state.health)
    logger.info("Service started", port={{ cookiecutter.http_port }})
    try:
        yield
    finally:
        await container.stop()
        shutdown_tracing()
        logger.info("Service stopped")


def create_app(
    settings: ServiceSettings | None = None,
    observability: ObservabilitySettings | None = None,
) -> FastAPI:
    """Assemble the application.

    Settings are arguments rather than module-level globals so a test can build
    an app without touching the environment.
    """
    service = settings or ServiceSettings()
    observe = observability or ObservabilitySettings()

    # Before the app object: an exception raised while building routes should
    # already come out as structured JSON with a trace id attached.
    configure_logging(service)
    configure_tracing(service, observe)

    app = FastAPI(
        title="{{ cookiecutter.description }}",
        version="0.1.0",
        lifespan=lifespan,
        # Probes are not part of the public contract and would only add noise
        # to the generated spec.
        openapi_url="/v1/openapi.json",
    )
    app.state.container = Container(service)
    app.state.health = HealthRegistry()

    _register_error_handler(app)
    _register_probes(app)
    return app


# No module-level `app`: building it requires a configured environment, and
# importing a module should never demand one. Uvicorn is told to call the
# factory instead — see the Dockerfile CMD.


def _register_error_handler(app: FastAPI) -> None:
    """One handler for everything, so no route can invent its own format."""

    @app.exception_handler(Exception)
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        status, body = envelope_from_exception(exc, trace_id=current_trace_id())
        if status >= 500:
            # Deliberate errors are already logged by the layer that raised
            # them; only the unexpected ones need a traceback here.
            logger.exception("Unhandled error", path=request.url.path)
        return JSONResponse(status_code=status, content=body)


def _register_probes(app: FastAPI) -> None:
    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness: the process answered. Touching a dependency here would
        let a database blip restart every pod."""
        return liveness()

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> Any:
        """Readiness: dependencies are reachable. Failing removes the pod from
        the load balancer, which is the right response to a dependency outage."""
        registry: HealthRegistry = app.state.health
        return require_ready(await registry.readiness())

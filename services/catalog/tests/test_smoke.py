"""The service starts, answers its probes, and never leaks an error.

Generated with the service, so a new service arrives with these properties
already asserted rather than assumed. Each one is something that is easy to
get wrong once per service and expensive to notice in production.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalog.main import create_app
from wb_platform.config import Environment, LogLevel, ObservabilitySettings, ServiceSettings
from wb_platform.errors import NotFoundError
from wb_platform.otel import shutdown_tracing


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuration the container needs to build.

    Values are placeholders — nothing connects here. `create_engine` is lazy,
    and the point of a smoke test is that the wiring holds, not that a database
    answers.
    """
    monkeypatch.setenv("DB_DSN", "postgresql+asyncpg://u:p@127.0.0.1:5432/test")
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
    monkeypatch.setenv("REDIS_DSN", "redis://127.0.0.1:6379/0")


@pytest.fixture
def app(configured: None) -> Iterator[FastAPI]:
    application = create_app(
        ServiceSettings(
            service_name="catalog",
            environment=Environment.LOCAL,
            log_level=LogLevel.WARNING,
        ),
        ObservabilitySettings(),
    )
    yield application
    shutdown_tracing()


class TestProbes:
    def test_liveness_answers_without_dependencies(self, app: FastAPI) -> None:
        """Kubernetes *restarts* what fails this probe.

        Touching a database here means a database blip restarts every pod of
        every service, discarding warm caches exactly when the database is
        already struggling.
        """
        with TestClient(app) as client:
            response = client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    def test_readiness_fails_when_a_dependency_is_unreachable(self, app: FastAPI) -> None:
        """The point of the probe: it must actually check something.

        A /readyz that answers 200 regardless is worse than none — it reports
        health it never examined, and the load balancer keeps sending traffic
        to a pod that cannot serve it.
        """
        with TestClient(app, raise_server_exceptions=False) as client:
            readiness = client.get("/readyz")
            liveness_response = client.get("/healthz")

        assert readiness.status_code == 503
        assert readiness.json()["error"]["code"] == "service_unavailable"
        # The separation that matters: a broken dependency must not restart
        # the pod, only remove it from the load balancer.
        assert liveness_response.status_code == 200

    def test_readiness_does_not_disclose_why(self, app: FastAPI) -> None:
        """Probe endpoints are commonly unauthenticated; a driver message
        carries the DSN, host and role."""
        with TestClient(app, raise_server_exceptions=False) as client:
            body = client.get("/readyz").text

        assert "5432" not in body
        assert "postgresql" not in body

    def test_probes_stay_out_of_the_public_schema(self, app: FastAPI) -> None:
        """They are operational, not part of the contract clients depend on."""
        with TestClient(app) as client:
            paths = client.get("/v1/openapi.json").json()["paths"]

        assert "/healthz" not in paths
        assert "/readyz" not in paths


class TestErrorEnvelope:
    def test_domain_errors_use_the_platform_envelope(self, app: FastAPI) -> None:
        @app.get("/v1/boom")
        async def boom() -> None:
            raise NotFoundError("Product not found.")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/v1/boom")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_unexpected_errors_disclose_nothing(self, app: FastAPI) -> None:
        """`str(exc)` routinely carries SQL, file paths and connection strings."""
        secret = 'relation "catalog_product" does not exist at /srv/app/repo.py:88'

        @app.get("/v1/kaboom")
        async def kaboom() -> None:
            raise RuntimeError(secret)

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/v1/kaboom")

        assert response.status_code == 500
        assert secret not in response.text
        assert "RuntimeError" not in response.text


class TestStartup:
    def test_importing_the_module_needs_no_configuration(self) -> None:
        """A module-level `app = create_app()` would demand SERVICE_NAME just
        to import — so the Dockerfile runs `--factory` instead."""
        from catalog import main

        assert not hasattr(main, "app")
        assert callable(main.create_app)

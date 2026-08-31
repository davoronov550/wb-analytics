"""Tests for liveness and readiness probes (T021).

The contract under test: an unreachable database fails ``/readyz`` and leaves
``/healthz`` untouched.

That separation is the point. Kubernetes *restarts* a container failing
liveness but only *removes it from the load balancer* on readiness. Wiring a
dependency into liveness means a database blip restarts every pod of every
service — discarding warm caches and connection pools at exactly the moment the
database is already struggling.
"""

from __future__ import annotations

import asyncio

import pytest

from wb_platform.errors import ServiceUnavailableError
from wb_platform.health import Check, HealthRegistry, liveness, require_ready


async def _ok() -> None:
    return None


def _failing(exc: Exception) -> Check:
    async def check() -> None:
        raise exc

    return check


class TestLiveness:
    def test_reports_ok_without_touching_anything(self) -> None:
        """Every dependency here is one that can restart the pod."""
        assert liveness() == {"status": "ok"}


class TestReadiness:
    @pytest.mark.asyncio
    async def test_all_checks_passing(self) -> None:
        registry = HealthRegistry()
        registry.register("database", _ok)
        registry.register("redis", _ok)

        report = await registry.readiness()

        assert report.ok is True
        assert report.as_dict() == {
            "status": "ok",
            "checks": {"database": "ok", "redis": "ok"},
        }

    @pytest.mark.asyncio
    async def test_one_failure_makes_the_service_not_ready(self) -> None:
        registry = HealthRegistry()
        registry.register("database", _failing(ConnectionError("connection refused")))
        registry.register("redis", _ok)

        report = await registry.readiness()

        assert report.ok is False
        assert report.as_dict()["checks"] == {"database": "failed", "redis": "ok"}

    @pytest.mark.asyncio
    async def test_every_failure_is_reported_not_just_the_first(self) -> None:
        """Sequential checks would name one dependency; usually you want all."""
        registry = HealthRegistry()
        registry.register("database", _failing(ConnectionError("a")))
        registry.register("redis", _failing(ConnectionError("b")))
        registry.register("kafka", _ok)

        report = await registry.readiness()

        assert {result.name for result in report.failures} == {"database", "redis"}

    @pytest.mark.asyncio
    async def test_with_no_checks_the_service_is_ready(self) -> None:
        """api-gateway holds no dependencies of its own."""
        assert (await HealthRegistry().readiness()).ok is True

    @pytest.mark.asyncio
    async def test_checks_run_concurrently(self) -> None:
        """Three dependencies at 2 s each must not make the probe take six."""
        registry = HealthRegistry(timeout_seconds=2.0)

        async def slow() -> None:
            await asyncio.sleep(0.15)

        for name in ("database", "redis", "clickhouse"):
            registry.register(name, slow)

        loop = asyncio.get_running_loop()
        started = loop.time()
        report = await registry.readiness()
        elapsed = loop.time() - started

        assert report.ok is True
        assert elapsed < 0.4  # sequential would be ≥ 0.45


class TestTimeout:
    @pytest.mark.asyncio
    async def test_a_hanging_check_fails_rather_than_hanging_the_probe(self) -> None:
        """A probe that never answers is worse than one that says "no".

        It also ties up a worker until the orchestrator's own timeout fires.
        """
        registry = HealthRegistry(timeout_seconds=0.05)

        async def hangs() -> None:
            await asyncio.sleep(10)

        registry.register("database", hangs)

        report = await registry.readiness()

        assert report.ok is False
        assert "timed out" in str(report.failures[0].detail)

    @pytest.mark.asyncio
    async def test_a_slow_check_does_not_block_the_others(self) -> None:
        registry = HealthRegistry(timeout_seconds=0.05)

        async def hangs() -> None:
            await asyncio.sleep(10)

        registry.register("database", hangs)
        registry.register("redis", _ok)

        report = await registry.readiness()

        assert {r.name: r.ok for r in report.checks} == {"database": False, "redis": True}


class TestDisclosure:
    @pytest.mark.asyncio
    async def test_the_response_body_names_checks_but_not_reasons(self) -> None:
        """Probe endpoints are commonly unauthenticated.

        A driver message carries the DSN, host and role; the body must not.
        """
        registry = HealthRegistry()
        registry.register(
            "database",
            _failing(ConnectionError("could not connect to wb_app@db:5432/wb_catalog")),
        )

        body = str((await registry.readiness()).as_dict())

        assert "wb_app" not in body
        assert "5432" not in body

    @pytest.mark.asyncio
    async def test_the_reason_is_kept_for_the_log(self) -> None:
        registry = HealthRegistry()
        registry.register("database", _failing(ConnectionError("connection refused")))

        (failure,) = (await registry.readiness()).failures

        assert "connection refused" in str(failure.detail)

    @pytest.mark.asyncio
    async def test_a_reasonless_exception_still_records_its_type(self) -> None:
        """TimeoutError's str() is empty — the same trap as in db.ping."""
        registry = HealthRegistry()
        registry.register("database", _failing(TimeoutError()))

        (failure,) = (await registry.readiness()).failures

        assert failure.detail == "TimeoutError"


class TestRequireReady:
    @pytest.mark.asyncio
    async def test_passes_through_when_ready(self) -> None:
        registry = HealthRegistry()
        registry.register("database", _ok)

        assert require_ready(await registry.readiness())["status"] == "ok"

    @pytest.mark.asyncio
    async def test_raises_the_platform_error_so_the_edge_answers_503(self) -> None:
        registry = HealthRegistry()
        registry.register("database", _failing(ConnectionError("down")))

        with pytest.raises(ServiceUnavailableError) as exc:
            require_ready(await registry.readiness())

        assert exc.value.http_status == 503
        assert "down" not in exc.value.message  # the reason stays in context


class TestRegistration:
    def test_duplicate_name_is_refused(self) -> None:
        """Two checks under one name would silently hide one of them."""
        registry = HealthRegistry()
        registry.register("database", _ok)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("database", _ok)

    def test_names_are_exposed_for_diagnostics(self) -> None:
        registry = HealthRegistry()
        registry.register("database", _ok)
        registry.register("redis", _ok)

        assert registry.names == ("database", "redis")

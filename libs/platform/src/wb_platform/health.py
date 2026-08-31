"""Liveness and readiness probes shared by every service (T021).

Two probes, and conflating them is the classic way to turn one broken
dependency into an outage.

* ``/healthz`` — **is the process alive?** Nothing else. Kubernetes *restarts*
  a container that fails it, so making it depend on PostgreSQL means a database
  blip restarts every pod of every service, which loses their warm caches and
  connection pools at the exact moment the database is struggling.
* ``/readyz`` — **can it serve traffic?** Kubernetes only removes the pod from
  the load balancer, which is the correct response to a dependency being down.

Checks run concurrently with a deadline. A readiness probe that hangs is
indistinguishable from one that fails, except that it also ties up a worker.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Final

from wb_platform.errors import ServiceUnavailableError

__all__ = [
    "Check",
    "HealthRegistry",
    "HealthReport",
    "ProbeResult",
    "liveness",
    "require_ready",
]

# A readiness probe is polled every few seconds; anything slower than this is
# already a failure from the load balancer's point of view.
DEFAULT_TIMEOUT_SECONDS: Final = 2.0

#: A check raises to signal failure and returns nothing to signal success.
Check = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ProbeResult:
    name: str
    ok: bool
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class HealthReport:
    ok: bool
    checks: tuple[ProbeResult, ...]

    def as_dict(self) -> dict[str, object]:
        """Body for the probe endpoint.

        Names and pass/fail only. The reason a dependency is down goes to the
        log: probe endpoints are commonly exposed without authentication, and
        a driver message carries the DSN, host and role.
        """
        return {
            "status": "ok" if self.ok else "unavailable",
            "checks": {result.name: ("ok" if result.ok else "failed") for result in self.checks},
        }

    @property
    def failures(self) -> tuple[ProbeResult, ...]:
        return tuple(result for result in self.checks if not result.ok)


def liveness() -> dict[str, str]:
    """``/healthz``: the process answered, so it is alive.

    Deliberately trivial. Every dependency this touches is one that can
    restart the pod.
    """
    return {"status": "ok"}


class HealthRegistry:
    """The dependency checks a service reports on ``/readyz``."""

    def __init__(self, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._checks: dict[str, Check] = {}
        self._timeout = timeout_seconds

    def register(self, name: str, check: Check) -> None:
        if name in self._checks:
            raise ValueError(f"Health check {name!r} is already registered.")
        self._checks[name] = check

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._checks)

    async def readiness(self) -> HealthReport:
        """Run every check concurrently and summarise.

        Concurrently, not in sequence: three dependencies at 2 s each would
        make the probe itself the slowest thing in the system, and a sequential
        run reports only the first failure when the useful answer is all of them.
        """
        if not self._checks:
            return HealthReport(ok=True, checks=())

        names = tuple(self._checks)
        outcomes = await asyncio.gather(
            *(self._run(self._checks[name]) for name in names),
            return_exceptions=False,
        )
        results = tuple(
            ProbeResult(name=name, ok=detail is None, detail=detail)
            for name, detail in zip(names, outcomes, strict=True)
        )
        return HealthReport(ok=all(result.ok for result in results), checks=results)

    async def _run(self, check: Check) -> str | None:
        """Return ``None`` on success, or a short reason for the log."""
        deadline = asyncio.timeout(self._timeout)
        try:
            async with deadline:
                await check()
        except TimeoutError:
            # Since Python 3.11 `asyncio.TimeoutError` *is* `TimeoutError`, so
            # catching it alone cannot tell "our deadline fired" from "the check
            # itself raised TimeoutError" — which db.ping does when a host is
            # unreachable. `expired()` is what separates a slow dependency from
            # one that refused immediately.
            if deadline.expired():
                return f"timed out after {self._timeout}s"
            return "TimeoutError"
        except Exception as exc:
            detail = str(exc)
            return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
        return None


def require_ready(report: HealthReport) -> Mapping[str, object]:
    """Raise :class:`ServiceUnavailableError` unless every check passed.

    Lets a handler answer the probe with the platform's normal error path
    instead of assembling a 503 by hand.
    """
    if not report.ok:
        raise ServiceUnavailableError(
            "Service is not ready.",
            context={"failed": {r.name: r.detail for r in report.failures}},
        )
    return report.as_dict()

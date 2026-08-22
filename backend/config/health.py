"""Health check endpoint (observability — Constitution VIII).

Reports reachability of the database and Redis (short timeouts). 200 when all
green, 503 when degraded, so orchestrators can gate traffic.
"""

from __future__ import annotations

import os

from django.db import connection
from django.http import HttpRequest, JsonResponse


def health_view(request: HttpRequest) -> JsonResponse:
    checks: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001 - health probe reports, never raises
        checks["database"] = "down"

    try:
        import redis

        client = redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=1,
        )
        client.ping()
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        checks["redis"] = "down"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )

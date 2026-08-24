"""DRF exception handler (inbound HTTP adapter).

Translates application/domain errors into safe HTTP responses without leaking
internals: UpstreamUnavailable → 502, InvalidFilter → 400.
Anything else falls through to DRF's default handler (validation → 400, unknown →
500 rendered by DRF).
"""

from __future__ import annotations

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from catalog.application.errors import InvalidFilter, UpstreamUnavailable

logger = logging.getLogger("catalog")


def exception_handler(exc: Exception, context: object) -> Response | None:
    if isinstance(exc, UpstreamUnavailable):
        logger.warning("Upstream Wildberries failure: %s", exc)
        return Response(
            {"detail": "Upstream Wildberries request failed."},
            status=502,
        )
    if isinstance(exc, InvalidFilter):
        return Response({"detail": str(exc)}, status=400)
    return drf_default_handler(exc, context)

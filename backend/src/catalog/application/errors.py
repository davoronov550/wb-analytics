"""Catalog application errors.

Adapters translate infrastructure failures into these; the HTTP exception handler
maps them to responses (e.g. UpstreamUnavailable → 502).
"""

from __future__ import annotations

__all__ = ["ApplicationError", "UpstreamUnavailable", "InvalidFilter"]


class ApplicationError(Exception):
    """Base class for catalog application-level errors."""


class UpstreamUnavailable(ApplicationError):
    """Wildberries was unreachable or returned an unusable payload."""


class InvalidFilter(ApplicationError):
    """Filter/ordering parameters failed validation."""

"""Reject NUL bytes in request payloads (inbound HTTP adapter).

PostgreSQL stores no NUL (0x00) in `text` or `jsonb`, while JSON strings and
Python `str` carry one without complaint. Every text field in the API is
therefore a 500 waiting for a client that sends one: the value passes
validation, reaches the INSERT, and psycopg raises `DataError` where nothing
catches it.

Checked once here rather than field by field. By the time this was written,
five out-of-range values had been fixed individually — each uncovered by the
fix before it — and NUL applies to every text column in the schema, so a
per-field rule would keep reproducing the defect at the next column.

Two entry points, because a NUL arrives in two different shapes:

* JSON escapes it as ``\u0000``, so the request bytes hold no 0x00 at all and
  only the decoded value shows it. ``NulRejectingJSONParser`` looks after
  decoding — which is also what distinguishes a real NUL from a client that
  sent the six literal characters ``\u0000`` as text, and that second one is
  an ordinary string the API must keep accepting.
* Form encodings put the byte in the body verbatim, where no decoding step
  would reveal it. ``RejectNulBytesMiddleware`` catches those.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

_API_PREFIX = "/api/"
_NUL = "\x00"
_MESSAGE = "Request body must not contain NUL (0x00) bytes."


def _contains_nul(value: Any) -> bool:
    """Walk a decoded JSON document. Keys count: `jsonb` refuses the escape
    wherever it appears, so a NUL in a key is as fatal as one in a value."""
    if isinstance(value, str):
        return _NUL in value
    if isinstance(value, dict):
        return any(_contains_nul(k) or _contains_nul(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_nul(item) for item in value)
    return False


class NulRejectingJSONParser(JSONParser):
    """`JSONParser` that refuses a decoded NUL instead of passing it to the DB."""

    def parse(
        self, stream: Any, media_type: str | None = None, parser_context: Any = None
    ) -> Any:
        # Delegate the decoding rather than reimplementing it: DRF reads its
        # own `rest_framework.utils.json`, honours STRICT_JSON and phrases the
        # parse error a particular way, and a copy of that here drifts from it
        # at the first upgrade.
        data = super().parse(stream, media_type, parser_context)
        if _contains_nul(data):
            raise ParseError(_MESSAGE)
        return data


class RejectNulBytesMiddleware:
    """400 for an /api/ request whose raw body carries a NUL byte.

    Covers the form encodings, where the byte travels verbatim and never passes
    through a decoder that would expose it.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith(_API_PREFIX) and b"\x00" in request.body:
            return JsonResponse({"detail": _MESSAGE}, status=400)
        return self._get_response(request)

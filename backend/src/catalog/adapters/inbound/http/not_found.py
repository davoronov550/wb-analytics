"""JSON 404 for API paths (inbound HTTP adapter).

Django answers an unmatched URL with an HTML error page. Inside `/api/` that
reaches a client which asked for JSON and gets a document it cannot parse — the
failure surfaces as a deserialization error rather than as "no such resource".

It is reachable without a typo in the client: `/api/schedules/<int:id>/` does
not match a non-numeric id, so any request with a malformed identifier leaves
the DRF stack before the view runs and never touches the exception handler that
would have produced an envelope.

Non-API paths keep Django's page — the admin and anything served alongside it
are read by browsers, not clients.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.defaults import page_not_found

_API_PREFIX = "/api/"


def not_found(
    request: HttpRequest, exception: Exception, template_name: str = "404.html"
) -> HttpResponse:
    if request.path.startswith(_API_PREFIX):
        return JsonResponse({"detail": "Not found."}, status=404)
    return page_not_found(request, exception, template_name=template_name)

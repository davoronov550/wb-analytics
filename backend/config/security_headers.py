"""Content-Security-Policy middleware.

A single static header, so a dedicated dependency would not earn its keep. The
policy is read from settings, which keeps it configurable per environment and
lets tests override it.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

HEADER = "Content-Security-Policy"


class ContentSecurityPolicyMiddleware:
    """Attach the configured CSP to every response.

    Django serves the JSON API and the HTML admin; the policy is what protects
    the admin if markup ever reflects untrusted input. An empty CSP_POLICY
    disables the header entirely.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self._get_response(request)
        policy = getattr(settings, "CSP_POLICY", "")
        if policy and HEADER not in response.headers:
            response.headers[HEADER] = policy
        return response

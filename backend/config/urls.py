"""Root URL configuration (framework glue).

Each bounded context exposes its own inbound HTTP adapter, mounted twice: under
`api/`, which is what exists today, and under `v1/`, which is the prefix the
FastAPI gateway will answer on.

The alias is what makes the cutover a routing change instead of an API change.
Clients move to `/v1/` while Django is still serving it, and when the gateway
takes over the prefix the request path they send does not change. Without it the
switch of backend and the switch of URL would have to happen in one step, and a
rollback would mean rolling back the frontend too.

Both prefixes reach the same view objects, so there is no second implementation
to keep in sync — `tests/e2e/test_v1_alias.py` asserts the two route sets stay
identical.

Removed in phase 5, when Django leaves the estate and `/api/` goes with it.
"""

from django.contrib import admin
from django.urls import include, path

from config.health import health_view

# Unmatched paths under the API prefixes answer with an envelope instead of
# Django's HTML page — see the handler's module docstring for why the HTML one
# is reachable at all.
handler404 = "catalog.adapters.inbound.http.not_found.not_found"

#: The inbound adapters, in mount order. Named once so the two prefixes cannot
#: drift apart by someone adding a context to one list and not the other.
_CONTEXT_URLCONFS = (
    "catalog.adapters.inbound.http.urls",
    "analytics.adapters.inbound.http.urls",
    "scheduling.adapters.inbound.http.urls",
    "notifications.adapters.inbound.http.urls",
    "accounts.adapters.inbound.http.urls",
)


def _aliased(urlconf: str) -> object:
    """Mount a context under `v1/` without colliding with its `/api/` names.

    Registering the same URLConf twice unnamespaced makes `reverse()` return
    whichever came last — a wrong URL, silently, at the first call site that
    uses it. Nothing calls `reverse()` today, which is exactly why the trap
    would go unnoticed until something did.
    """
    context = urlconf.split(".", 1)[0]
    return include((urlconf, f"v1_{context}"), namespace=f"v1_{context}")


urlpatterns = [
    path("admin/", admin.site.urls),
    # Not versioned: liveness is infrastructure, not part of the product API,
    # and the gateway will answer its own.
    path("api/health/", health_view, name="health"),
    # --- context API routers ---
    *(path("api/", include(urlconf)) for urlconf in _CONTEXT_URLCONFS),
    *(path("v1/", _aliased(urlconf)) for urlconf in _CONTEXT_URLCONFS),
]

"""Root URL configuration (framework glue).

Each bounded context exposes its own inbound HTTP adapter under `api/`. Those
includes are enabled as their view tasks land, so the URLConf imports cleanly at
every step.
"""

from django.contrib import admin
from django.urls import include, path

from config.health import health_view

# Unmatched paths under /api/ answer with an envelope instead of Django's
# HTML page — see the module docstring for why the HTML one is reachable.
handler404 = "catalog.adapters.inbound.http.not_found.not_found"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_view, name="health"),
    # --- context API routers ---
    path("api/", include("catalog.adapters.inbound.http.urls")),
    path("api/", include("analytics.adapters.inbound.http.urls")),
    path("api/", include("scheduling.adapters.inbound.http.urls")),
    path("api/", include("notifications.adapters.inbound.http.urls")),
    path("api/", include("accounts.adapters.inbound.http.urls")),
]

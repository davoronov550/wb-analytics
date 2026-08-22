"""Root URL configuration (framework glue).

Each bounded context exposes its own inbound HTTP adapter under `api/`. Those
includes are enabled as their view tasks land, so the URLConf imports cleanly at
every step.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- context API routers: enable as each context's views land ---
    path("api/", include("catalog.adapters.inbound.http.urls")),  # T038/T058
    path("api/", include("analytics.adapters.inbound.http.urls")),  # T068/T073/T090
    path("api/", include("scheduling.adapters.inbound.http.urls")),  # T063
    path("api/", include("notifications.adapters.inbound.http.urls")),  # T086
    path("api/", include("accounts.adapters.inbound.http.urls")),  # T076
    # path("api/health/", health_view),  # T095
]

"""Root URL configuration (framework glue).

Each bounded context exposes its own inbound HTTP adapter under `api/`. Those
includes are enabled as their view tasks land, so the URLConf imports cleanly at
every step.
"""
from django.contrib import admin
from django.urls import path

# from django.urls import include

urlpatterns = [
    path("admin/", admin.site.urls),
    # --- context API routers: enable as each context's views land ---
    # path("api/", include("catalog.adapters.inbound.http.urls")),         # T038 (products), T058 (parse/tasks)
    # path("api/", include("analytics.adapters.inbound.http.urls")),       # T068 history, T073 stats, T090 export
    # path("api/", include("scheduling.adapters.inbound.http.urls")),      # T063 schedules
    # path("api/", include("notifications.adapters.inbound.http.urls")),   # T086 alerts
    # path("api/", include("accounts.adapters.inbound.http.urls")),        # T076 auth + saved searches
    # path("api/health/", health_view),                                    # T095 observability
]

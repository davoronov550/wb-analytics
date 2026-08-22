"""
Django settings — framework glue only (Constitution III).

Business logic lives in the bounded-context packages under `src/`; this module
just wires Django/DRF/CORS/Celery and registers each context's persistence app.
Context apps and their URL includes are added incrementally as their model/view
tasks land (see the task references below), so the project boots at every step.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party (adapters only)
    "rest_framework",
    "django_filters",
    "corsheaders",
    # --- bounded-context persistence apps: enable each as its model task lands ---
    "catalog.adapters.outbound.persistence.apps.CatalogPersistenceConfig",  # T015 (+ ParseJob T057)
    "catalog.adapters.inbound.cli.apps.CatalogCliConfig",  # T028 (management commands)
    "analytics.adapters.outbound.persistence.apps.AnalyticsPersistenceConfig",  # T067
    "scheduling.adapters.outbound.persistence.apps.SchedulingPersistenceConfig",  # T062
    "notifications.adapters.outbound.persistence.apps.NotificationsPersistenceConfig",  # T084
    "accounts.adapters.outbound.persistence.apps.AccountsPersistenceConfig",  # T075
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


def _database_from_env() -> dict:
    """Build the default DB config from DATABASE_URL, or a local PG default.

    `manage.py check` does not open a connection, so the default keeps the
    project bootable before the DB env is set (see .env.example, task T004).
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "wb_analytics",
            "USER": "postgres",
            "PASSWORD": "postgres",
            "HOST": "localhost",
            "PORT": "5432",
        }
    parsed = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }


DATABASES = {"default": _database_from_env()}
# Fail fast when the DB is unreachable (keeps `check`/`makemigrations` snappy
# before PostgreSQL is up); real usage overrides via DATABASE_URL/pool settings.
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 2

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework (inbound HTTP adapter defaults) ---
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 1000,  # charts need the full filtered set; per-view cap in T038/T040
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",  # catalog reads are public (FR-044)
    ],
    "EXCEPTION_HANDLER": "catalog.adapters.inbound.http.exceptions.exception_handler",  # T020
}

# --- CORS (frontend dev origin) ---
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ORIGIN", "http://localhost:5173").split(",") if o
]

# --- Celery (async + scheduled work; adapters in T056/T057/T063) ---
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
CELERY_TASK_STORE_EAGER_RESULT = True

# --- Wildberries gateway (adapter reads these; T026/T052/T053) ---
WB_MAX_PAGES = int(os.environ.get("WB_MAX_PAGES", "10"))
WB_DEST = os.environ.get("WB_DEST", "-1257786")
WB_REQUEST_TIMEOUT = float(os.environ.get("WB_REQUEST_TIMEOUT", "10"))
WB_PROXIES = [p for p in os.environ.get("WB_PROXIES", "").split(",") if p]

# --- Event bus wiring switch (in-process now, message-bus later; seam) ---
EVENT_PUBLISHER = os.environ.get("EVENT_PUBLISHER", "inprocess")

# --- Price-history retention (FE-04; T066) ---
SNAPSHOT_RETENTION_DAYS = int(os.environ.get("SNAPSHOT_RETENTION_DAYS", "90"))

# --- Notifications (FE-07; T085) ---
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
SMTP_FROM = os.environ.get("SMTP_FROM", "alerts@example.com")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "alerts@example.com")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID", "")
ALERT_COOLDOWN_SECONDS = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "21600"))

# --- Auth / JWT (FE-09) ---
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY") or SECRET_KEY,
}

# --- Structured logging (Constitution VIII) ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {
        # Per-context loggers (catalog, analytics, ...) inherit the console handler.
        "catalog": {"level": "INFO"},
    },
}

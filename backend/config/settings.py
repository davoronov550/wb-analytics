"""
Django settings — framework glue only.

Business logic lives in the bounded-context packages under `src/`; this module
just wires Django/DRF/CORS/Celery and registers each context's persistence app.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_dotenv(path: Path) -> None:
    """Minimal, dependency-free .env loader: `KEY=value` lines, `#` comments.
    Real environment variables always win (never overridden), so container/CI
    config takes precedence over the local file."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(BASE_DIR / ".env")

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
    # --- bounded-context persistence apps ---
    "catalog.adapters.outbound.persistence.apps.CatalogPersistenceConfig",
    "catalog.adapters.inbound.cli.apps.CatalogCliConfig",  # management commands
    "analytics.adapters.outbound.persistence.apps.AnalyticsPersistenceConfig",
    "scheduling.adapters.outbound.persistence.apps.SchedulingPersistenceConfig",
    "notifications.adapters.outbound.persistence.apps.NotificationsPersistenceConfig",
    "accounts.adapters.outbound.persistence.apps.AccountsPersistenceConfig",
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
    project bootable before the DB env is set (see .env.example).
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
_db_options = DATABASES["default"].setdefault("OPTIONS", {})
# Fail fast when the DB is unreachable (keeps `check`/`makemigrations` snappy
# before PostgreSQL is up); real usage overrides via DATABASE_URL/pool settings.
_db_options["connect_timeout"] = 2
# Encrypt the app↔PostgreSQL link. `disable` suits a local container; production
# should set `verify-full` so the server certificate and hostname are checked.
_db_options["sslmode"] = os.environ.get("DB_SSLMODE", "disable")

# Reuse connections across requests instead of reconnecting every time (a new
# TCP + auth handshake per request is pure overhead). CONN_HEALTH_CHECKS is the
# required companion: without it Django can hand out a connection the server has
# already dropped.
DATABASES["default"]["CONN_MAX_AGE"] = int(os.environ.get("DB_CONN_MAX_AGE", "60"))
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

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
    "PAGE_SIZE": 1000,  # charts need the full filtered set
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",  # catalog reads are public
    ],
    "EXCEPTION_HANDLER": "catalog.adapters.inbound.http.exceptions.exception_handler",
    # Rate limits for abuse-prone endpoints (scoped throttles opt in per view).
    "DEFAULT_THROTTLE_RATES": {
        "parse": os.environ.get("THROTTLE_PARSE", "30/min"),
        "auth": os.environ.get("THROTTLE_AUTH", "10/min"),
    },
}

# --- CORS (frontend dev origin) ---
CORS_ALLOWED_ORIGINS = [
    o
    for o in os.environ.get("CORS_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o
]

# --- Celery (async + scheduled work) ---
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = (
    "pytest" in sys.modules  # run tasks inline under pytest (deterministic, no worker)
    or os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
)
CELERY_TASK_STORE_EAGER_RESULT = True

# --- Caching ---
# Redis in normal runs; in-memory under pytest so the suite needs no broker.
_TESTING = "pytest" in sys.modules
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
            if _TESTING
            else "django.core.cache.backends.redis.RedisCache"
        ),
        "LOCATION": (
            "wb-analytics-locmem"
            if _TESTING
            else os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        ),
    }
}
# Aggregating the whole filtered set (avg/median/stddev) is the most expensive read
# in the app and /api/stats/ is public, so the result is cached. Seconds; 0 disables
# caching entirely (the default under pytest, so tests exercise the real query).
STATS_CACHE_TTL = int(os.environ.get("STATS_CACHE_TTL", "0" if _TESTING else "120"))

# --- Wildberries gateway (adapter reads these) ---
WB_MAX_PAGES = int(os.environ.get("WB_MAX_PAGES", "10"))
WB_DEST = os.environ.get("WB_DEST", "-1257786")
WB_REQUEST_TIMEOUT = float(os.environ.get("WB_REQUEST_TIMEOUT", "10"))
WB_PROXIES = [p for p in os.environ.get("WB_PROXIES", "").split(",") if p]

# --- Event bus wiring switch (in-process now, message-bus later; seam) ---
EVENT_PUBLISHER = os.environ.get("EVENT_PUBLISHER", "inprocess")

# --- Price-history retention ---
SNAPSHOT_RETENTION_DAYS = int(os.environ.get("SNAPSHOT_RETENTION_DAYS", "90"))

# --- Notifications ---
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

# --- Auth / JWT ---
# Google OAuth web client ID; required to verify "Continue with Google" ID tokens.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": os.environ.get("JWT_SIGNING_KEY") or SECRET_KEY,
}

# --- HTTPS / cookie hardening ---
# All driven by env so local development over plain HTTP keeps working, while a
# production profile satisfies `manage.py check --deploy`.
_SECURE_DEFAULT = "false" if DEBUG else "true"


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).lower() == "true"


# Tell browsers to only ever reach this origin over HTTPS. Enable deliberately:
# a wrong value is remembered by the browser for the whole max-age.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _flag("SECURE_HSTS_INCLUDE_SUBDOMAINS", _SECURE_DEFAULT)
SECURE_HSTS_PRELOAD = _flag("SECURE_HSTS_PRELOAD", _SECURE_DEFAULT)
SECURE_SSL_REDIRECT = _flag("SECURE_SSL_REDIRECT", _SECURE_DEFAULT)
# Behind a TLS-terminating proxy Django must be told what the original scheme was.
if os.environ.get("USE_X_FORWARDED_PROTO", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = _flag("SESSION_COOKIE_SECURE", _SECURE_DEFAULT)
CSRF_COOKIE_SECURE = _flag("CSRF_COOKIE_SECURE", _SECURE_DEFAULT)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # the SPA must read this token to send it back

# Refuse to boot a production instance on the shipped placeholder key.
if not DEBUG and SECRET_KEY == "dev-insecure-change-me":
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is still the development placeholder. "
        "Generate a unique value before running with DEBUG=false."
    )

# --- Structured logging ---
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

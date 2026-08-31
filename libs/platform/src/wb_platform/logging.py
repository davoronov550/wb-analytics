"""Structured logging shared by every service (T011).

Three decisions this module exists to enforce, all of them things that are
cheap now and impossible to retrofit during an incident:

1. **Context travels by contextvars, not by argument.** ``trace_id``,
   ``service`` and ``owner_id`` attach themselves to every record. Threading
   them through call signatures is what teams intend and fail to do; the first
   function that forgets is the one that breaks the correlation chain.
2. **Third-party records use the same pipeline.** aiokafka, SQLAlchemy and
   uvicorn log through stdlib ``logging``. Left alone they emit unparseable
   text with no correlation id — precisely the half of the output that matters
   when the broker misbehaves. Everything is routed through
   ``ProcessorFormatter`` so one handler governs all of it.
3. **Secrets are redacted in the pipeline, not at call sites.** A rule that
   depends on every developer remembering it is not a rule.

Renderer choice follows the environment: JSON everywhere, except ``local``,
where a human is reading a terminal and JSON helps nobody.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator, MutableMapping
from contextlib import contextmanager
from typing import Any, Final, TextIO

import orjson
import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from wb_platform.config import Environment, LogLevel, ServiceSettings

__all__ = [
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_logger",
    "log_context",
]

# Values under these keys are replaced wholesale. Matching is case-insensitive
# and on the exact key, not a substring: a substring rule would silently redact
# `token_count` or `password_policy` and make diagnostics worse, not better.
_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "credentials",
        "csrf",
        "id_token",
        "password",
        "passwd",
        "private_key",
        "refresh_token",
        "secret",
        "session",
        "set-cookie",
        "token",
        "x-api-key",
    }
)

_REDACTED: Final = "***"

# Types that cannot hide a credential in their text form. Listed to avoid
# calling str() on every number in every record.
_OPAQUE_SCALARS: Final = (bool, int, float, bytes, type(None))

# `scheme://user:password@host` — the password is stripped, the user kept.
# Knowing *which* role failed to connect is diagnostic; its password is not.
_URL_CREDENTIALS: Final = re.compile(r"(?P<prefix>://[^:/@\s]+:)(?P<secret>[^@/\s]+)(?=@)")

_LEVELS: Final[dict[LogLevel, int]] = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
}


def _serialize(obj: Any, /, **kwargs: Any) -> str:
    """orjson serializer adapted to structlog's ``json.dumps`` signature.

    orjson returns bytes and takes no ``ensure_ascii``/``sort_keys``; both are
    dropped deliberately. Russian text stays readable in the log, which matters
    because search queries are the data we most often grep for.
    """
    default = kwargs.get("default")
    return orjson.dumps(obj, default=default).decode()


def _strip_url_credentials(text: str) -> str:
    return _URL_CREDENTIALS.sub(rf"\g<prefix>{_REDACTED}", text)


def _redact(value: Any) -> Any:
    """Strip credentials from a value, recursing into containers."""
    if isinstance(value, str):
        return _strip_url_credentials(value)
    if isinstance(value, MutableMapping):
        return {k: (_REDACTED if _is_sensitive(k) else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        # Always a list: JSON has one array type, so the tuple-ness carries no
        # information into the log, and rebuilding exotic tuple subclasses
        # (NamedTuple) from a generator would fail.
        return [_redact(item) for item in value]
    if isinstance(value, _OPAQUE_SCALARS):
        return value
    # Objects whose *text* form embeds credentials. Pydantic's PostgresDsn and
    # RedisDsn are the ones actually hit: redaction runs before serialization,
    # so without this branch the renderer prints their repr — password and all.
    # Verified to leak before this branch existed.
    text = str(value)
    return _strip_url_credentials(text) if _URL_CREDENTIALS.search(text) else value


def _is_sensitive(key: Any) -> bool:
    return isinstance(key, str) and key.lower() in _SENSITIVE_KEYS


def _redact_secrets(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Processor: no credential reaches the log, whatever the call site did."""
    return {k: (_REDACTED if _is_sensitive(k) else _redact(v)) for k, v in event_dict.items()}


def _service_stamp(service_name: str) -> Processor:
    """Processor factory: pin the service name onto every record.

    A closure rather than bound context: context can be cleared, and a record
    without a service name is unattributable in aggregated logs.
    """

    def processor(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
        event_dict["service"] = service_name
        return event_dict

    return processor


def _shared_processors(service_name: str) -> list[Processor]:
    """Applied to structlog and stdlib records alike, in this order."""
    return [
        structlog.contextvars.merge_contextvars,
        _service_stamp(service_name),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        # Structured exception data instead of an embedded newline-ridden
        # string: a traceback that breaks the one-record-per-line contract is
        # unusable in Loki.
        structlog.processors.dict_tracebacks,
        _redact_secrets,
    ]


def _renderer(environment: Environment) -> Processor:
    if environment is Environment.LOCAL:
        return structlog.dev.ConsoleRenderer(colors=False)
    return structlog.processors.JSONRenderer(serializer=_serialize)


def configure_logging(settings: ServiceSettings, *, stream: TextIO | None = None) -> None:
    """Install the logging pipeline. Call once, from the composition root.

    ``stream`` exists for tests; production writes to stdout, which is what a
    container runtime collects.
    """
    level = _LEVELS[settings.log_level]
    shared = _shared_processors(settings.service_name)

    structlog.configure(
        processors=[
            *shared,
            # Hands the event dict to ProcessorFormatter, which does the
            # rendering — the single place where both pipelines converge.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # Caching a bound logger would survive reconfiguration and make the
        # pipeline unreconfigurable in tests. JSON serialization dominates the
        # cost anyway, so the optimisation buys nothing measurable.
        cache_logger_on_first_use=False,
    )

    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            # Records from libraries that never touched structlog still need
            # the service name, timestamp and redaction.
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                _renderer(settings.environment),
            ],
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers on import; leaving them attached
    # duplicates every access log line, once formatted and once not.
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(noisy)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a logger. Prefer the module name at the call site."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


def bind_context(**fields: Any) -> None:
    """Attach fields to every subsequent record in this task.

    Scoped to the current asyncio task, so concurrent requests never borrow
    each other's trace id.
    """
    structlog.contextvars.bind_contextvars(**fields)


def clear_context() -> None:
    """Drop all bound fields — call when a request or consumer loop ends."""
    structlog.contextvars.clear_contextvars()


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    """Bind fields for the duration of a block, restoring what they shadowed."""
    tokens = structlog.contextvars.bind_contextvars(**fields)
    try:
        yield
    finally:
        structlog.contextvars.reset_contextvars(**tokens)

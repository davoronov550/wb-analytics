"""Command idempotency via ``Idempotency-Key`` (T017).

Replaces the current ``find_active(query)`` check, which only prevents two
*simultaneous* collections of the same text. It does nothing for the case that
actually happens: a client times out, retries, and the first request had already
succeeded — so the work runs twice and the caller still sees an error.

Three outcomes, and the middle one is the one people forget:

* **Same key, same body** → the stored response is replayed. The retry is free.
* **Same key, *different* body** → 409. Reusing a key for different content is a
  client bug; answering 200 with the old response would hide it.
* **Same key, still running** → 409 with ``retry_after``. Two concurrent
  requests must not both do the work.

The store is Redis, keyed by ``key`` and namespaced per service so two services
cannot collide on a key a client reused across them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Protocol, Self

from wb_platform.errors import ConflictError

__all__ = [
    "DEFAULT_TTL_SECONDS",
    "IdempotencyStore",
    "RedisLike",
    "StoredResponse",
]

# A retry that arrives a day later is a new request, not a duplicate. Longer
# retention would keep responses for clients that no longer exist.
DEFAULT_TTL_SECONDS: Final = 24 * 60 * 60

# How long a caller is told to wait when the original request is still running.
_IN_PROGRESS_RETRY_AFTER: Final = 2


class _State(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class RedisLike(Protocol):
    """The three Redis operations this module needs.

    A Protocol rather than the concrete client so the semantics can be tested
    without a server, and so a service that already holds a connection pool can
    pass it in.
    """

    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None: ...

    async def get(self, name: str) -> str | bytes | None: ...

    async def delete(self, *names: str) -> int: ...


@dataclass(frozen=True, slots=True)
class StoredResponse:
    """A completed response, replayed verbatim on a matching retry."""

    status: int
    body: Any

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "body": self.body}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(status=int(raw["status"]), body=raw.get("body"))


def _fingerprint(body: Any) -> str:
    """Stable hash of the request body.

    ``sort_keys`` matters: two JSON objects with the same content in a
    different key order are the same request, and a client library is free to
    reorder them between the original and the retry.
    """
    material = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(material.encode()).hexdigest()


class IdempotencyStore:
    """Redis-backed record of what each ``Idempotency-Key`` produced."""

    def __init__(
        self,
        redis: RedisLike,
        *,
        namespace: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._redis = redis
        self._namespace = namespace
        self._ttl = ttl_seconds

    def _redis_key(self, key: str) -> str:
        # Namespaced per service: a client reusing one key across api-gateway
        # and export must not have one answer the other's request.
        return f"idempotency:{self._namespace}:{key}"

    async def begin(self, key: str, body: Any) -> StoredResponse | None:
        """Claim the key before doing the work.

        Returns the stored response when this is a replay of a completed
        request, and ``None`` when the caller should proceed. Raises
        :class:`ConflictError` when the key is in use for different content or
        the original request is still running.
        """
        fingerprint = _fingerprint(body)
        claimed = await self._redis.set(
            self._redis_key(key),
            json.dumps({"state": _State.IN_PROGRESS, "fingerprint": fingerprint}),
            ex=self._ttl,
            nx=True,
        )
        if claimed:
            return None

        return self._interpret(await self._load(key), key=key, fingerprint=fingerprint)

    def _interpret(
        self, record: dict[str, Any] | None, *, key: str, fingerprint: str
    ) -> StoredResponse | None:
        if record is None:
            # The record expired between SET NX failing and the read. Rare, and
            # letting the request through is the safe reading: at worst the work
            # repeats, which is what happens today without idempotency at all.
            return None

        if record.get("fingerprint") != fingerprint:
            raise ConflictError(
                "Idempotency-Key was already used for a different request body.",
                context={"key": key},
            )

        if record.get("state") == _State.IN_PROGRESS:
            raise ConflictError(
                "A request with this Idempotency-Key is still in progress.",
                retry_after=_IN_PROGRESS_RETRY_AFTER,
                context={"key": key},
            )

        return StoredResponse.from_dict(record["response"])

    async def complete(self, key: str, body: Any, response: StoredResponse) -> None:
        """Record the outcome so a later retry replays it instead of redoing it."""
        await self._redis.set(
            self._redis_key(key),
            json.dumps(
                {
                    "state": _State.COMPLETED,
                    "fingerprint": _fingerprint(body),
                    "response": response.as_dict(),
                },
                ensure_ascii=False,
            ),
            ex=self._ttl,
        )

    async def release(self, key: str) -> None:
        """Drop the claim after a failure, so the caller may retry.

        Without this a failed request would block its own key for a day: the
        record says "in progress" and nothing ever completes it.
        """
        await self._redis.delete(self._redis_key(key))

    async def _load(self, key: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._redis_key(key))
        if raw is None:
            return None
        text = raw.decode() if isinstance(raw, bytes) else raw
        loaded: dict[str, Any] = json.loads(text)
        return loaded

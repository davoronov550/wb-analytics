"""Tests for command idempotency (T017).

The contract under test: a retry with the same key and body replays the stored
response; the same key with a different body is refused.

The second half is what the current ``find_active(query)`` cannot express. It
prevents two simultaneous collections of the same text and nothing else — so
the case that actually happens (client times out, retries, the original had
already succeeded) still runs the work twice and still returns an error.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from wb_platform.errors import ConflictError
from wb_platform.idempotency import IdempotencyStore, StoredResponse


class FakeRedis:
    """Enough Redis to exercise the semantics: SET with NX, GET, DELETE."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int | None] = {}

    async def set(
        self, name: str, value: str, *, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if nx and name in self.values:
            return None
        self.values[name] = value
        self.expirations[name] = ex
        return True

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def delete(self, *names: str) -> int:
        return sum(self.values.pop(name, None) is not None for name in names)


@pytest.fixture
def store() -> IdempotencyStore:
    return IdempotencyStore(FakeRedis(), namespace="ingestion")


BODY = {"query": "наушники", "max_pages": 3}
RESPONSE = StoredResponse(status=202, body={"task_id": "abc", "status": "pending"})


class TestFirstRequest:
    @pytest.mark.asyncio
    async def test_proceeds_when_the_key_is_new(self, store: IdempotencyStore) -> None:
        assert await store.begin("key-1", BODY) is None


class TestReplay:
    @pytest.mark.asyncio
    async def test_same_key_and_body_replays_the_stored_response(
        self, store: IdempotencyStore
    ) -> None:
        await store.begin("key-1", BODY)
        await store.complete("key-1", BODY, RESPONSE)

        replayed = await store.begin("key-1", BODY)

        assert replayed == RESPONSE

    @pytest.mark.asyncio
    async def test_replay_preserves_the_status_code(self, store: IdempotencyStore) -> None:
        """202 must stay 202 — the client branches on it."""
        await store.begin("key-1", BODY)
        await store.complete("key-1", BODY, RESPONSE)

        replayed = await store.begin("key-1", BODY)

        assert replayed is not None
        assert replayed.status == 202

    @pytest.mark.asyncio
    async def test_key_order_in_the_body_does_not_break_the_match(
        self, store: IdempotencyStore
    ) -> None:
        """A client library is free to reorder JSON keys between attempts."""
        await store.begin("key-1", {"query": "наушники", "max_pages": 3})
        await store.complete("key-1", {"query": "наушники", "max_pages": 3}, RESPONSE)

        replayed = await store.begin("key-1", {"max_pages": 3, "query": "наушники"})

        assert replayed == RESPONSE


class TestConflicts:
    @pytest.mark.asyncio
    async def test_same_key_with_a_different_body_is_refused(self, store: IdempotencyStore) -> None:
        """Answering 200 with the old response would hide a client bug."""
        await store.begin("key-1", BODY)
        await store.complete("key-1", BODY, RESPONSE)

        with pytest.raises(ConflictError) as exc:
            await store.begin("key-1", {"query": "чайник", "max_pages": 3})

        assert exc.value.http_status == 409

    @pytest.mark.asyncio
    async def test_concurrent_request_with_the_same_key_is_refused(
        self, store: IdempotencyStore
    ) -> None:
        """Two in-flight requests must not both do the work."""
        await store.begin("key-1", BODY)

        with pytest.raises(ConflictError) as exc:
            await store.begin("key-1", BODY)

        assert exc.value.retry_after is not None

    @pytest.mark.asyncio
    async def test_conflict_does_not_disclose_the_stored_body(
        self, store: IdempotencyStore
    ) -> None:
        await store.begin("key-1", {"secret_query": "внутреннее"})

        with pytest.raises(ConflictError) as exc:
            await store.begin("key-1", {"other": 1})

        assert "внутреннее" not in exc.value.message


class TestRelease:
    @pytest.mark.asyncio
    async def test_failed_request_frees_its_key(self, store: IdempotencyStore) -> None:
        """Without release the key stays 'in progress' for a day and blocks itself."""
        await store.begin("key-1", BODY)
        await store.release("key-1")

        assert await store.begin("key-1", BODY) is None


class TestIsolation:
    @pytest.mark.asyncio
    async def test_namespaces_keep_services_apart(self) -> None:
        """A client reusing one key across services must not cross answers."""
        redis = FakeRedis()
        ingestion = IdempotencyStore(redis, namespace="ingestion")
        export = IdempotencyStore(redis, namespace="export")

        await ingestion.begin("key-1", BODY)

        assert await export.begin("key-1", BODY) is None

    @pytest.mark.asyncio
    async def test_ttl_is_applied_to_every_write(self) -> None:
        redis = FakeRedis()
        store = IdempotencyStore(redis, namespace="ingestion", ttl_seconds=3600)

        await store.begin("key-1", BODY)
        await store.complete("key-1", BODY, RESPONSE)

        assert set(redis.expirations.values()) == {3600}


class TestExpiryRace:
    @pytest.mark.asyncio
    async def test_record_vanishing_mid_check_lets_the_request_through(self) -> None:
        """SET NX fails, then the record expires before the read.

        Rare, and letting the request proceed is the safe reading: at worst the
        work repeats, which is exactly what happens today with no idempotency.
        """
        redis = FakeRedis()
        store = IdempotencyStore(redis, namespace="ingestion")
        await store.begin("key-1", BODY)
        redis.values.clear()  # the TTL fires between the SET and the GET

        assert await store.begin("key-1", BODY) is None


class TestStoredResponse:
    def test_round_trips_through_the_stored_form(self) -> None:
        restored = StoredResponse.from_dict(json.loads(json.dumps(RESPONSE.as_dict())))

        assert restored == RESPONSE

    def test_accepts_a_body_of_any_json_shape(self) -> None:
        for body in ({"a": 1}, [1, 2], "text", 42, None):
            payload: Any = StoredResponse(status=200, body=body).as_dict()
            assert StoredResponse.from_dict(payload).body == body

"""Gateway resilience tests (T051) — offline via respx. RED before T052/T053.

Covers retry with backoff on 429/timeout, User-Agent rotation across attempts, and
mapping of exhausted retries to UpstreamUnavailable. Backoff sleep is a no-op so
tests are fast and deterministic.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from catalog.adapters.outbound.wildberries.gateway import HttpxWbCatalogGateway
from catalog.application.errors import UpstreamUnavailable

_FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "wb_search.json").read_text(encoding="utf-8")
)
_EMPTY = {"data": {"products": []}}


def _gateway(**overrides) -> HttpxWbCatalogGateway:
    kwargs = {
        "sleep": lambda _seconds: None,
        "jitter": lambda: 0.0,
        "max_retries": 3,
        "user_agents": ["UA-A", "UA-B", "UA-C", "UA-D"],
    }
    kwargs.update(overrides)
    return HttpxWbCatalogGateway(**kwargs)


@respx.mock
def test_retries_on_429_then_succeeds():
    route = respx.route(method="GET", host="search.wb.ru").mock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(200, json=_FIXTURE),
            httpx.Response(200, json=_EMPTY),
        ]
    )
    raws = _gateway().fetch("наушники", max_pages=5)
    assert [r.wb_id for r in raws] == [179421376, 180002233]
    assert route.call_count == 3


@respx.mock
def test_retries_on_timeout_then_succeeds():
    route = respx.route(method="GET", host="search.wb.ru").mock(
        side_effect=[
            httpx.TimeoutException("timed out"),
            httpx.Response(200, json=_FIXTURE),
            httpx.Response(200, json=_EMPTY),
        ]
    )
    raws = _gateway().fetch("q", max_pages=5)
    assert len(raws) == 2
    assert route.call_count == 3


@respx.mock
def test_raises_upstream_unavailable_after_exhausting_retries_on_429():
    respx.route(method="GET", host="search.wb.ru").mock(return_value=httpx.Response(429))
    with pytest.raises(UpstreamUnavailable):
        _gateway(max_retries=2).fetch("q", max_pages=1)


@respx.mock
def test_raises_upstream_unavailable_after_exhausting_retries_on_timeout():
    respx.route(method="GET", host="search.wb.ru").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    with pytest.raises(UpstreamUnavailable):
        _gateway(max_retries=1).fetch("q", max_pages=1)


@respx.mock
def test_rotates_user_agent_across_attempts():
    captured: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("user-agent"))
        if len(captured) < 2:
            return httpx.Response(429)
        return httpx.Response(200, json=_EMPTY)

    respx.route(method="GET", host="search.wb.ru").mock(side_effect=handler)
    _gateway(user_agents=["UA-A", "UA-B", "UA-C"]).fetch("q", max_pages=1)

    assert captured[0] == "UA-A"
    assert captured[1] == "UA-B"

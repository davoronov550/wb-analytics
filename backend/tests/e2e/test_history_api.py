"""E2E tests (T068) for price history — REQUIRE PostgreSQL (@django_db, deferred).

Exercises the full event seam: a collection run publishes ProductsCollected, the
analytics subscriber records a snapshot, and the history endpoint returns it.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx
from rest_framework.test import APIClient

_FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "wb_search.json").read_text(encoding="utf-8")
)
_EMPTY = {"data": {"products": []}}


@pytest.mark.django_db
def test_empty_history_returns_ok():
    resp = APIClient().get("/api/products/999/history/")
    assert resp.status_code == 200
    assert resp.data["points"] == []


@pytest.mark.django_db
@respx.mock
def test_collection_records_a_snapshot_visible_in_history():
    respx.route(method="GET", host="search.wb.ru").mock(
        side_effect=[httpx.Response(200, json=_FIXTURE), httpx.Response(200, json=_EMPTY)]
    )
    client = APIClient()

    started = client.post("/api/parse/", {"query": "наушники"}, format="json")
    assert started.status_code == 202  # eager task ran → snapshot recorded via the event seam

    history = client.get("/api/products/179421376/history/")
    assert history.status_code == 200
    assert len(history.data["points"]) == 1
    assert history.data["points"][0]["sale_price"] == "2999.00"

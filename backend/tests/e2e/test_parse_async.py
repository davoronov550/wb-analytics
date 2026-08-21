"""E2E tests (T055) for async collection: POST /api/parse/ + GET /api/tasks/{id}/.

The happy path and the 404 lookup require the DB (@django_db, deferred until
PostgreSQL is up). The missing-query 400 validation runs offline. The happy path
mocks Wildberries via respx (the eager Celery task would otherwise hit the network).

Run the deferred tests with:
    docker compose up -d db
    .venv/Scripts/python -m pytest tests/e2e/test_parse_async.py
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


def test_parse_requires_query():
    resp = APIClient().post("/api/parse/", {}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
@respx.mock
def test_parse_returns_202_then_task_completes():
    respx.route(method="GET", host="search.wb.ru").mock(
        side_effect=[httpx.Response(200, json=_FIXTURE), httpx.Response(200, json=_EMPTY)]
    )
    client = APIClient()

    resp = client.post("/api/parse/", {"query": "наушники"}, format="json")
    assert resp.status_code == 202
    task_id = resp.data["task_id"]

    status = client.get(f"/api/tasks/{task_id}/")
    assert status.status_code == 200
    assert status.data["status"] == "done"  # Celery eager → already finished
    assert status.data["collected_count"] == 2


@pytest.mark.django_db
def test_unknown_task_returns_404():
    resp = APIClient().get("/api/tasks/does-not-exist/")
    assert resp.status_code == 404

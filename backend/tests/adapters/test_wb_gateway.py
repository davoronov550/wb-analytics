"""Gateway adapter test — offline via respx against a recorded fixture.

 Verifies parsing (kopecks kept), pagination until an empty page,
and the max_pages bound. Never hits the live Wildberries service.
"""

import json
from pathlib import Path

import httpx
import respx

from catalog.adapters.outbound.wildberries.gateway import HttpxWbCatalogGateway

_FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "wb_search.json").read_text(encoding="utf-8")
)
_EMPTY = {"data": {"products": []}}


@respx.mock
def test_fetch_parses_and_paginates_until_empty_page():
    route = respx.route(method="GET", host="search.wb.ru").mock(
        side_effect=[
            httpx.Response(200, json=_FIXTURE),
            httpx.Response(200, json=_EMPTY),
        ]
    )

    raws = HttpxWbCatalogGateway().fetch("наушники", max_pages=5)

    assert [r.wb_id for r in raws] == [179421376, 180002233]
    assert raws[0].price_kopecks == 599900
    assert raws[0].sale_price_kopecks == 299900
    assert raws[1].price_kopecks == 1000000  # legacy priceU fallback
    assert route.call_count == 2  # page 1 (data) + page 2 (empty → stop)


@respx.mock
def test_fetch_respects_max_pages_bound():
    route = respx.route(method="GET", host="search.wb.ru").mock(
        return_value=httpx.Response(200, json=_FIXTURE)  # every page non-empty
    )

    raws = HttpxWbCatalogGateway().fetch("q", max_pages=3)

    assert route.call_count == 3
    assert len(raws) == 6  # 3 pages × 2 products

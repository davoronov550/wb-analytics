"""Unit tests for WB payload parsing — no network, no DB."""

from catalog.adapters.outbound.wildberries.payload import parse_search_response


def test_prefers_sizes_price_and_falls_back_to_legacy_fields():
    data = {
        "data": {
            "products": [
                {
                    "id": 1,
                    "name": "A",
                    "sizes": [{"price": {"basic": 599900, "product": 299900}}],
                    "reviewRating": 4.7,
                    "feedbacks": 1234,
                },
                {
                    "id": 2,
                    "name": "B",
                    "priceU": 1000000,
                    "salePriceU": 850000,
                    "rating": 4.1,
                    "feedbacks": 50,
                },
            ]
        }
    }
    a, b = parse_search_response(data)
    assert (a.wb_id, a.price_kopecks, a.sale_price_kopecks, a.rating, a.reviews) == (
        1,
        599900,
        299900,
        4.7,
        1234,
    )
    assert (b.wb_id, b.price_kopecks, b.sale_price_kopecks, b.rating, b.reviews) == (
        2,
        1000000,
        850000,
        4.1,
        50,
    )


def test_skips_records_missing_id_or_name():
    data = {
        "data": {
            "products": [
                {"name": "no id"},
                {"id": 3},
                {"id": 4, "name": "ok", "priceU": 100},
            ]
        }
    }
    assert [r.wb_id for r in parse_search_response(data)] == [4]


def test_parses_top_level_products_wb_v9():
    # WB v9 returns products at the top level (not nested under "data").
    data = {
        "products": [
            {
                "id": 245763655,
                "name": "Наушники",
                "sizes": [{"price": {"basic": 337800, "product": 182000}}],
                "reviewRating": 4.8,
                "feedbacks": 539,
            }
        ],
        "total": 100,
    }
    (raw,) = parse_search_response(data)
    assert raw.wb_id == 245763655
    assert raw.price_kopecks == 337800
    assert raw.sale_price_kopecks == 182000
    assert raw.reviews == 539


def test_empty_or_malformed_response_returns_empty():
    assert parse_search_response({}) == []
    assert parse_search_response({"data": {}}) == []
    assert parse_search_response(None) == []

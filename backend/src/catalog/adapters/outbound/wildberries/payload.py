"""Parse a Wildberries catalog-search JSON payload into RawProducts.

All WB-format knowledge (field names, price fallbacks) lives here. Prices are kept
as kopecks (the use case normalizes to rubles via Money.from_kopecks). Records
without an id or name are skipped — the use case never sees them.
"""

from __future__ import annotations

from catalog.application.dto import RawProduct


def _price_kopecks(product: dict, size_key: str, legacy_key: str) -> int | None:
    """Prefer current v9 location ``sizes[0].price.<size_key>``; fall back to the
    legacy top-level field (e.g. priceU / salePriceU)."""
    sizes = product.get("sizes") or []
    if sizes:
        price = sizes[0].get("price") or {}
        value = price.get(size_key)
        if value is not None:
            return value
    return product.get(legacy_key)


def parse_search_response(data: dict | None) -> list[RawProduct]:
    root = data or {}
    # WB v9 returns products at the top level; older payloads nest them under "data".
    products = root.get("products")
    if products is None:
        products = (root.get("data") or {}).get("products")
    products = products or []
    result: list[RawProduct] = []
    for product in products:
        wb_id = product.get("id")
        name = product.get("name")
        if not wb_id or not name:
            continue
        result.append(
            RawProduct(
                wb_id=wb_id,
                name=name,
                price_kopecks=_price_kopecks(product, "basic", "priceU"),
                sale_price_kopecks=_price_kopecks(product, "product", "salePriceU"),
                rating=product.get("reviewRating", product.get("rating")),
                reviews=product.get("feedbacks"),
            )
        )
    return result

"""Query parameters of the product endpoints, declared once.

``parse_product_filter`` and ``parse_ordering`` read the request dictionary by
hand, so nothing connects the parameters the API accepts to the parameters the
schema advertises. Writing the list twice — once in the parser, once in
``@extend_schema`` — guarantees the two drift apart at the first edit, and the
drift is invisible: the schema keeps validating, it just describes a different
API than the one running.

So the list lives here, both the decorators and a test import it, and
``test_schema_params.py`` fails when the parser starts reading a key this
module does not declare.
"""

from __future__ import annotations

from typing import Final

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from catalog.application.dto import ORDERABLE_FIELDS

#: Every key ``parse_product_filter`` reads. Kept as bare strings so the drift
#: test can compare them against the parser without unpacking OpenAPI objects.
FILTER_PARAM_NAMES: Final[frozenset[str]] = frozenset(
    {
        "min_price",
        "max_price",
        "min_rating",
        "max_rating",
        "min_reviews",
        "max_reviews",
        "query",
    }
)

#: Keys ``parse_ordering`` reads.
ORDERING_PARAM_NAMES: Final[frozenset[str]] = frozenset({"ordering"})

#: Keys the list view reads directly, outside either parser.
PAGINATION_PARAM_NAMES: Final[frozenset[str]] = frozenset({"page", "page_size"})


def _query(
    name: str, type_: OpenApiTypes | dict[str, object], description: str, **extra: object
) -> OpenApiParameter:
    return OpenApiParameter(
        name=name, type=type_, location=OpenApiParameter.QUERY, description=description, **extra
    )


# Bounds the parsers already enforce. Declaring them is not decoration: a schema
# that omits them says `page=0` is valid input, so every client generated from
# it — and every contract test — treats the resulting 400 as a server defect.
# `schemathesis` reports exactly that, which is how these came to be written.
#
# Cross-parameter rules (`min_price <= max_price` and the two like it) have no
# expression in an OpenAPI parameter schema and stay 400-only; see the note in
# `docs/migration/02-functional-parity.md`.
_PRICE = {"type": "number", "format": "double", "minimum": 0}
_RATING = {"type": "number", "format": "double", "minimum": 0, "maximum": 5}
_COUNT = {"type": "integer", "minimum": 0}


#: Price bounds apply to `sale_price` — what the buyer pays, not the list
#: price. Documented because the name does not say it and the difference is
#: visible to anyone filtering by price.
FILTER_PARAMETERS: Final[list[OpenApiParameter]] = [
    _query("min_price", _PRICE, "Lower bound on the discounted price."),
    _query("max_price", _PRICE, "Upper bound on the discounted price."),
    _query("min_rating", _RATING, "Lower bound on rating."),
    _query("max_rating", _RATING, "Upper bound on rating."),
    _query("min_reviews", _COUNT, "Lower bound on the review count."),
    _query("max_reviews", _COUNT, "Upper bound on the review count."),
    _query("query", OpenApiTypes.STR, "Restrict to products collected for this search query."),
]

ORDERING_PARAMETERS: Final[list[OpenApiParameter]] = [
    _query(
        "ordering",
        OpenApiTypes.STR,
        "Sort field, optionally prefixed with '-' for descending. "
        f"One of: {', '.join(sorted(ORDERABLE_FIELDS))}.",
        enum=sorted(ORDERABLE_FIELDS) + [f"-{field}" for field in sorted(ORDERABLE_FIELDS)],
    ),
]

PAGINATION_PARAMETERS: Final[list[OpenApiParameter]] = [
    _query("page", {"type": "integer", "minimum": 1}, "1-based page number."),
    _query(
        "page_size",
        # No `maximum`: a larger value is clamped to 1000, not refused. Declaring
        # the cap here would say the API rejects it, and a contract test would
        # then read the accepted request as a missing validation.
        {"type": "integer", "minimum": 1},
        "Rows per page. Values above 1000 are clamped to 1000 rather than "
        "refused; the cap exists because the charts are computed client-side "
        "from this response.",
    ),
]

#: What `GET /api/products/` accepts.
PRODUCT_LIST_PARAMETERS: Final[list[OpenApiParameter]] = [
    *FILTER_PARAMETERS,
    *ORDERING_PARAMETERS,
    *PAGINATION_PARAMETERS,
]

#: What `/api/stats/` and `/api/export/` accept — no pagination, and `query`
#: may repeat on stats to request a comparison.
ANALYTICS_PARAMETERS: Final[list[OpenApiParameter]] = [*FILTER_PARAMETERS]

DECLARED_PARAM_NAMES: Final[frozenset[str]] = (
    FILTER_PARAM_NAMES | ORDERING_PARAM_NAMES | PAGINATION_PARAM_NAMES
)

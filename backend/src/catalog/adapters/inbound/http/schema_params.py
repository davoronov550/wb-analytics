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
    name: str, type_: OpenApiTypes, description: str, **extra: object
) -> OpenApiParameter:
    return OpenApiParameter(
        name=name, type=type_, location=OpenApiParameter.QUERY, description=description, **extra
    )


#: Price bounds apply to `sale_price` — what the buyer pays, not the list
#: price. Documented because the name does not say it and the difference is
#: visible to anyone filtering by price.
FILTER_PARAMETERS: Final[list[OpenApiParameter]] = [
    _query("min_price", OpenApiTypes.DECIMAL, "Lower bound on the discounted price."),
    _query("max_price", OpenApiTypes.DECIMAL, "Upper bound on the discounted price."),
    _query("min_rating", OpenApiTypes.DECIMAL, "Lower bound on rating, within [0, 5]."),
    _query("max_rating", OpenApiTypes.DECIMAL, "Upper bound on rating, within [0, 5]."),
    _query("min_reviews", OpenApiTypes.INT, "Lower bound on the review count."),
    _query("max_reviews", OpenApiTypes.INT, "Upper bound on the review count."),
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
    _query("page", OpenApiTypes.INT, "1-based page number."),
    _query(
        "page_size",
        OpenApiTypes.INT,
        "Rows per page, capped at 1000. The cap exists because the charts are "
        "computed client-side from this response.",
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

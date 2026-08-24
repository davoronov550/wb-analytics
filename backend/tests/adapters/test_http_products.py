"""HTTP request-parsing tests — query params → ProductFilter/Ordering.

 Parsing/validation is pure (no DB); invalid input raises
InvalidFilter, which the exception handler maps to 400.
"""

from decimal import Decimal

import pytest

from catalog.adapters.inbound.http.request_filters import parse_ordering, parse_product_filter
from catalog.application.dto import Ordering
from catalog.application.errors import InvalidFilter


class TestParseProductFilter:
    def test_parses_all_filters(self):
        result = parse_product_filter(
            {
                "min_price": "5000",
                "max_price": "20000",
                "min_rating": "4",
                "max_rating": "4.8",
                "min_reviews": "100",
                "max_reviews": "900",
                "query": "наушники",
            }
        )
        assert result.min_price == Decimal("5000")
        assert result.max_price == Decimal("20000")
        assert result.min_rating == Decimal("4")
        assert result.max_rating == Decimal("4.8")
        assert result.min_reviews == 100
        assert result.max_reviews == 900
        assert result.query == "наушники"

    def test_min_rating_greater_than_max_rating_raises(self):
        with pytest.raises(InvalidFilter):
            parse_product_filter({"min_rating": "4.5", "max_rating": "4.0"})

    def test_min_reviews_greater_than_max_reviews_raises(self):
        with pytest.raises(InvalidFilter):
            parse_product_filter({"min_reviews": "100", "max_reviews": "50"})

    def test_empty_params_yield_all_none(self):
        result = parse_product_filter({})
        assert (
            result.min_price,
            result.max_price,
            result.min_rating,
            result.min_reviews,
            result.query,
        ) == (None, None, None, None, None)

    def test_min_price_greater_than_max_price_raises(self):
        with pytest.raises(InvalidFilter):
            parse_product_filter({"min_price": "100", "max_price": "50"})

    def test_non_numeric_price_raises(self):
        with pytest.raises(InvalidFilter):
            parse_product_filter({"min_price": "abc"})

    def test_rating_out_of_range_raises(self):
        with pytest.raises(InvalidFilter):
            parse_product_filter({"min_rating": "9"})

    def test_negative_reviews_raises(self):
        with pytest.raises(InvalidFilter):
            parse_product_filter({"min_reviews": "-5"})


class TestParseOrdering:
    def test_default_is_reviews_count_descending(self):
        result = parse_ordering({})
        assert isinstance(result, Ordering)
        assert result.field == "reviews_count"
        assert result.descending is True

    def test_ascending(self):
        result = parse_ordering({"ordering": "price"})
        assert result.field == "price"
        assert result.descending is False

    def test_descending(self):
        result = parse_ordering({"ordering": "-rating"})
        assert result.field == "rating"
        assert result.descending is True

    def test_invalid_field_raises(self):
        with pytest.raises(InvalidFilter):
            parse_ordering({"ordering": "wb_id"})

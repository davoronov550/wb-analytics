"""Domain unit tests for shared value objects (pure — no Django, no DB).

RED first: `shared.domain.value_objects` is.

Contract:
- Constructors are STRICT (raise ValueError on invalid input) — domain purity.
- `.coerce(raw)` is the LENIENT boundary parser for dirty Wildberries data
  (non-numeric / out-of-range → safe default), used by the WB gateway adapter.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from shared.domain.value_objects import Money, Rating, ReviewsCount


class TestMoney:
    def test_from_kopecks_divides_by_100(self):
        assert Money.from_kopecks(299900).amount == Decimal("2999.00")

    def test_direct_amount_quantized_to_two_places(self):
        assert Money(Decimal("10")).amount == Decimal("10.00")

    def test_negative_amount_raises(self):
        with pytest.raises(ValueError):
            Money(Decimal("-0.01"))

    def test_negative_kopecks_raises(self):
        with pytest.raises(ValueError):
            Money.from_kopecks(-100)

    def test_equality_by_value(self):
        assert Money.from_kopecks(1000) == Money(Decimal("10.00"))

    def test_ordering(self):
        assert Money(Decimal("5")) < Money(Decimal("10"))

    def test_subtraction_returns_money(self):
        assert Money(Decimal("30")) - Money(Decimal("10")) == Money(Decimal("20.00"))

    def test_is_immutable(self):
        m = Money(Decimal("5.00"))
        with pytest.raises(FrozenInstanceError):
            m.amount = Decimal("9.00")  # type: ignore[misc]


class TestRating:
    def test_valid_value_kept(self):
        assert Rating(Decimal("4.7")).value == Decimal("4.7")

    def test_quantized_to_one_place(self):
        assert Rating(4).value == Decimal("4.0")

    @pytest.mark.parametrize("bad", [Decimal("-0.1"), Decimal("5.1"), 6])
    def test_out_of_range_raises(self, bad):
        with pytest.raises(ValueError):
            Rating(bad)

    def test_coerce_parses_and_clamps(self):
        assert Rating.coerce("4.5").value == Decimal("4.5")
        assert Rating.coerce(9).value == Decimal("5.0")
        assert Rating.coerce(-2).value == Decimal("0.0")

    def test_coerce_non_numeric_defaults_to_zero(self):
        assert Rating.coerce("abc").value == Decimal("0.0")
        assert Rating.coerce(None).value == Decimal("0.0")


class TestReviewsCount:
    def test_valid(self):
        assert ReviewsCount(1234).value == 1234

    def test_zero_ok(self):
        assert ReviewsCount(0).value == 0

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            ReviewsCount(-1)

    def test_coerce_parses(self):
        assert ReviewsCount.coerce("1234").value == 1234
        assert ReviewsCount.coerce(12.9).value == 12

    def test_coerce_bad_defaults_to_zero(self):
        assert ReviewsCount.coerce("abc").value == 0
        assert ReviewsCount.coerce(-5).value == 0
        assert ReviewsCount.coerce(None).value == 0

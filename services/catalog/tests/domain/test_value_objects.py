"""Domain unit tests for shared value objects (pure — no Django, no DB).

RED first: `catalog.domain.value_objects` is.

Contract:
- Constructors are STRICT (raise ValueError on invalid input) — domain purity.
- `.coerce(raw)` is the LENIENT boundary parser for dirty Wildberries data
  (non-numeric / out-of-range → safe default), used by the WB gateway adapter.
"""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from catalog.domain.value_objects import Money, Rating, ReviewsCount


class TestMoney:
    def test_from_kopecks_divides_by_100(self) -> None:
        assert Money.from_kopecks(299900).amount == Decimal("2999.00")

    def test_direct_amount_quantized_to_two_places(self) -> None:
        assert Money(Decimal("10")).amount == Decimal("10.00")

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(ValueError):
            Money(Decimal("-0.01"))

    def test_negative_kopecks_raises(self) -> None:
        with pytest.raises(ValueError):
            Money.from_kopecks(-100)

    def test_equality_by_value(self) -> None:
        assert Money.from_kopecks(1000) == Money(Decimal("10.00"))

    def test_ordering(self) -> None:
        assert Money(Decimal("5")) < Money(Decimal("10"))

    def test_subtraction_returns_money(self) -> None:
        assert Money(Decimal("30")) - Money(Decimal("10")) == Money(Decimal("20.00"))

    def test_is_immutable(self) -> None:
        m = Money(Decimal("5.00"))
        with pytest.raises(FrozenInstanceError):
            m.amount = Decimal("9.00")  # type: ignore[misc]


class TestRating:
    def test_valid_value_kept(self) -> None:
        assert Rating(Decimal("4.7")).value == Decimal("4.7")

    def test_quantized_to_one_place(self) -> None:
        # `int` on purpose. The field says `Decimal` and `__post_init__` runs
        # it through `_to_decimal`, which accepts int/str/float — so the
        # constructor is wider than its annotation. Kept as a test rather
        # than widened in the domain: the declared lenient path is
        # `Rating.coerce`, and the domain moves by copying (CLAUDE.md, п. 6).
        assert Rating(4).value == Decimal("4.0")  # type: ignore[arg-type]

    # `6` is an int for the same reason as above: the range check runs after
    # coercion, so an out-of-range int must raise like an out-of-range Decimal.
    @pytest.mark.parametrize("bad", [Decimal("-0.1"), Decimal("5.1"), 6])
    def test_out_of_range_raises(self, bad: Decimal | int) -> None:
        with pytest.raises(ValueError):
            Rating(bad)  # type: ignore[arg-type]

    def test_coerce_parses_and_clamps(self) -> None:
        assert Rating.coerce("4.5").value == Decimal("4.5")
        assert Rating.coerce(9).value == Decimal("5.0")
        assert Rating.coerce(-2).value == Decimal("0.0")

    def test_coerce_non_numeric_defaults_to_zero(self) -> None:
        assert Rating.coerce("abc").value == Decimal("0.0")
        assert Rating.coerce(None).value == Decimal("0.0")


class TestReviewsCount:
    def test_valid(self) -> None:
        assert ReviewsCount(1234).value == 1234

    def test_zero_ok(self) -> None:
        assert ReviewsCount(0).value == 0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            ReviewsCount(-1)

    def test_coerce_parses(self) -> None:
        assert ReviewsCount.coerce("1234").value == 1234
        assert ReviewsCount.coerce(12.9).value == 12

    def test_coerce_bad_defaults_to_zero(self) -> None:
        assert ReviewsCount.coerce("abc").value == 0
        assert ReviewsCount.coerce(-5).value == 0
        assert ReviewsCount.coerce(None).value == 0

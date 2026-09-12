"""`Ordering` is a list of sort keys, not one field (T110).

The backend sorted by a single field while `SortBuilder.tsx` built any number of
levels and shipped only the first to the server. The rest was applied in the
browser, over the same thousand-row page — the third instance of one cause,
alongside pagination and histograms (док. 2, §2.3).

Server-side pagination makes that arrangement impossible: a page ordered by one
level and then re-sorted by the client contains the wrong rows, not merely rows
in the wrong order. So the list has to reach the server whole.

This is the one sanctioned edit to the copied application layer
(док. 7, §7.6), which is why the backward-compatible spelling is tested as
carefully as the new one: `Ordering(field=...)` has to keep working, or the
edit stops being an extension and becomes a rewrite.
"""

from __future__ import annotations

import pytest

from catalog.application.dto import ORDERABLE_FIELDS, Ordering, SortKey


class TestTheOldSpellingStillWorks:
    """Every construction the copied tests use."""

    def test_no_arguments_keeps_the_previous_default(self) -> None:
        assert Ordering().keys == (SortKey("reviews_count", descending=True),)

    def test_a_single_field_becomes_a_list_of_one(self) -> None:
        assert Ordering(field="price").keys == (SortKey("price", descending=True),)

    def test_direction_is_carried_over(self) -> None:
        assert Ordering(field="price", descending=False).keys == (
            SortKey("price", descending=False),
        )

    def test_an_unknown_field_is_still_refused(self) -> None:
        """The check existed before this change and must not be lost in it."""
        with pytest.raises(ValueError, match="Cannot order by"):
            Ordering(field="colour")


class TestTheListForm:
    def test_keys_are_kept_in_order(self) -> None:
        """Order is the whole meaning of the structure: `rating` then
        `reviews_count` is a different sort from the reverse."""
        ordering = Ordering(
            keys=(SortKey("rating", descending=True), SortKey("reviews_count", descending=True))
        )

        assert [key.field for key in ordering.keys] == ["rating", "reviews_count"]

    def test_directions_may_be_mixed(self) -> None:
        """The interface preset that makes tuple comparison wrong: ascending
        price, then descending rating."""
        ordering = Ordering(
            keys=(SortKey("sale_price", descending=False), SortKey("rating", descending=True))
        )

        assert [key.descending for key in ordering.keys] == [False, True]

    def test_every_field_in_the_list_is_checked(self) -> None:
        with pytest.raises(ValueError, match="Cannot order by"):
            Ordering(keys=(SortKey("rating"), SortKey("colour")))

    def test_an_empty_list_is_refused(self) -> None:
        """An ordering with no keys has no defined page boundary, so keyset
        pagination over it repeats and skips rows."""
        with pytest.raises(ValueError, match="at least one"):
            Ordering(keys=())


class TestTheTwoSpellingsDoNotMix:
    def test_giving_both_is_refused(self) -> None:
        """Silently preferring one would make the other a no-op — and the
        no-op would be a sort the caller believes is applied."""
        with pytest.raises(ValueError, match="not both"):
            Ordering(keys=(SortKey("rating"),), field="price")


class TestOrderableFieldsAreUnchanged:
    def test_the_vocabulary_did_not_grow(self) -> None:
        """§7.6 is explicit: the structure changes, the set of fields does not."""
        assert ORDERABLE_FIELDS == frozenset(
            {"price", "sale_price", "rating", "reviews_count", "name"}
        )

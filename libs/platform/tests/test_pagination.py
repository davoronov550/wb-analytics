"""Tests for keyset pagination (T015).

The contract under test: paging through a sorted set with **any** combination
of sort directions yields every row exactly once, in the same order a full
sort would produce.

Why this needs a property test rather than examples. The tuple-comparison
shortcut — ``WHERE (a, b) < (:a, :b)`` — is correct only while every level
sorts the same way, and the interface ships a preset that does not
("Дешевле ↑ + рейтинг ↓"). The failure it produces is not a crash: rows on a
page boundary quietly vanish or repeat, and only for particular data. Examples
chosen by hand tend to miss exactly that, so the ordering is checked against an
independent implementation — Python's ``sorted`` — over generated data.
"""

from __future__ import annotations

import base64
import json
import operator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wb_platform.errors import ValidationError
from wb_platform.pagination import (
    MAX_PAGE_SIZE,
    Comparison,
    Page,
    PageRequest,
    SortKey,
    SortSpec,
    build_page,
    decode_cursor,
    encode_cursor,
    keyset_predicate,
    order_by,
)

_TIEBREAK = SortKey("external_id", descending=True)


def _spec(*keys: SortKey, tiebreaker: SortKey = _TIEBREAK) -> SortSpec:
    return SortSpec(keys=keys, tiebreaker=tiebreaker)


def _forge_cursor(spec: SortSpec, entries: list[list[str]]) -> str:
    """Build a structurally valid cursor with hand-picked contents.

    Used to reach the decoder's rejection paths, which a well-formed cursor
    never exercises — and which are exactly what a tampering client hits.
    """
    payload = {"v": 1, "f": spec.fingerprint(), "k": entries}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


# --------------------------------------------------------------------------
# Sort specification
# --------------------------------------------------------------------------


class TestSortSpec:
    def test_tiebreaker_is_always_the_last_key(self) -> None:
        """Structurally impossible to forget — a separate field, not a convention.

        Without a unique final key, rows sharing every sorted value order
        differently between queries, and pagination either loops or skips.
        """
        spec = _spec(SortKey("rating", descending=True))

        assert spec.all_keys == (SortKey("rating", descending=True), _TIEBREAK)

    def test_sorting_by_tiebreaker_alone_is_allowed(self) -> None:
        assert _spec().all_keys == (_TIEBREAK,)

    def test_repeated_field_is_rejected(self) -> None:
        """The interface disables an already-used field; the server must too."""
        with pytest.raises(ValidationError) as exc:
            _spec(SortKey("rating"), SortKey("rating", descending=True))

        assert "rating" in str(exc.value)

    def test_field_colliding_with_the_tiebreaker_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _spec(SortKey("external_id"))

    def test_fingerprint_changes_with_direction(self) -> None:
        """A cursor must not survive a change of sort — see TestCursor."""
        ascending = _spec(SortKey("price", descending=False))
        descending = _spec(SortKey("price", descending=True))

        assert ascending.fingerprint() != descending.fingerprint()

    def test_fingerprint_is_stable_across_equal_specs(self) -> None:
        assert _spec(SortKey("price")).fingerprint() == _spec(SortKey("price")).fingerprint()


class TestOrderBy:
    def test_emits_every_key_including_the_tiebreaker(self) -> None:
        spec = _spec(SortKey("sale_price"), SortKey("rating", descending=True))

        assert order_by(spec) == (
            ("sale_price", False),
            ("rating", True),
            ("external_id", True),
        )


# --------------------------------------------------------------------------
# Predicate construction
# --------------------------------------------------------------------------


class TestKeysetPredicate:
    def test_single_descending_key_compares_with_less_than(self) -> None:
        spec = _spec()
        predicate = keyset_predicate(spec, {"external_id": 100})

        assert predicate == ((Comparison("external_id", "<", 100),),)

    def test_single_ascending_key_compares_with_greater_than(self) -> None:
        spec = _spec(tiebreaker=SortKey("external_id", descending=False))
        predicate = keyset_predicate(spec, {"external_id": 100})

        assert predicate == ((Comparison("external_id", ">", 100),),)

    def test_mixed_directions_expand_into_a_chain(self) -> None:
        """The case tuple comparison cannot express: `sale_price ↑, rating ↓`."""
        spec = _spec(SortKey("sale_price"), SortKey("rating", descending=True))

        predicate = keyset_predicate(
            spec, {"sale_price": Decimal("1000"), "rating": Decimal("4.5"), "external_id": 7}
        )

        assert predicate == (
            (Comparison("sale_price", ">", Decimal("1000")),),
            (
                Comparison("sale_price", "=", Decimal("1000")),
                Comparison("rating", "<", Decimal("4.5")),
            ),
            (
                Comparison("sale_price", "=", Decimal("1000")),
                Comparison("rating", "=", Decimal("4.5")),
                Comparison("external_id", "<", 7),
            ),
        )

    def test_conjunction_count_matches_key_count(self) -> None:
        spec = _spec(SortKey("a"), SortKey("b"), SortKey("c"))
        values = {"a": 1, "b": 2, "c": 3, "external_id": 4}

        assert len(keyset_predicate(spec, values)) == 4

    def test_missing_cursor_value_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            keyset_predicate(_spec(SortKey("rating")), {"external_id": 1})

    def test_null_cursor_value_is_rejected(self) -> None:
        """`NULL < x` is NULL, so a nullable sort column silently drops rows.

        Refusing here beats returning a page that is quietly short.
        """
        with pytest.raises(ValidationError) as exc:
            keyset_predicate(_spec(SortKey("rating")), {"rating": None, "external_id": 1})

        assert "rating" in str(exc.value)


# --------------------------------------------------------------------------
# Cursor
# --------------------------------------------------------------------------


class TestCursor:
    def test_round_trips_preserving_types(self) -> None:
        spec = _spec(SortKey("sale_price"), SortKey("reviews_count"))
        values = {"sale_price": Decimal("1234.50"), "reviews_count": 42, "external_id": 999}

        assert decode_cursor(spec, encode_cursor(spec, values)) == values

    def test_preserves_decimal_precision(self) -> None:
        """Money round-tripped through float would drift — and it is money."""
        spec = _spec(SortKey("price"))
        restored = decode_cursor(
            spec, encode_cursor(spec, {"price": Decimal("0.10"), "external_id": 1})
        )

        assert restored["price"] == Decimal("0.10")
        assert isinstance(restored["price"], Decimal)

    @pytest.mark.parametrize(
        "value",
        [
            42,
            -7,
            "наушники",
            3.5,
            True,
            False,
            Decimal("-0.01"),
            datetime(2026, 8, 31, 12, 30, 5, tzinfo=UTC),
            date(2026, 8, 31),
        ],
    )
    def test_every_supported_type_survives_the_round_trip(self, value: Any) -> None:
        """A cursor that changes a value's type compares against the wrong thing."""
        spec = _spec(SortKey("field"))
        restored = decode_cursor(spec, encode_cursor(spec, {"field": value, "external_id": 1}))

        assert restored["field"] == value
        assert type(restored["field"]) is type(value)

    def test_unsupported_value_type_is_rejected_at_encode_time(self) -> None:
        """Fail where the mistake is, not on the next request that decodes it."""
        with pytest.raises(ValidationError) as exc:
            encode_cursor(_spec(SortKey("field")), {"field": {1, 2}, "external_id": 1})

        assert "set" in str(exc.value)

    def test_unknown_type_tag_is_rejected(self) -> None:
        forged = _forge_cursor(_spec(), [["external_id", "zz", "1"]])

        with pytest.raises(ValidationError):
            decode_cursor(_spec(), forged)

    def test_payload_that_is_not_an_object_is_rejected(self) -> None:
        encoded = base64.urlsafe_b64encode(b"[1, 2, 3]").decode().rstrip("=")

        with pytest.raises(ValidationError):
            decode_cursor(_spec(), encoded)

    def test_entries_that_are_not_a_list_are_rejected(self) -> None:
        payload = {"v": 1, "f": _spec().fingerprint(), "k": "nope"}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        with pytest.raises(ValidationError):
            decode_cursor(_spec(), encoded)

    def test_malformed_entry_shape_is_rejected(self) -> None:
        forged = _forge_cursor(_spec(), [["external_id", "i"]])

        with pytest.raises(ValidationError):
            decode_cursor(_spec(), forged)

    def test_cursor_from_a_future_version_is_rejected(self) -> None:
        payload = {"v": 99, "f": _spec().fingerprint(), "k": [["external_id", "i", "1"]]}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

        with pytest.raises(ValidationError) as exc:
            decode_cursor(_spec(), encoded)

        assert "version" in str(exc.value).lower()

    def test_is_opaque_to_the_client(self) -> None:
        """Values must not be guessable from the string, or clients will build them."""
        cursor = encode_cursor(_spec(), {"external_id": 12345})

        assert "12345" not in cursor

    def test_cursor_from_a_different_sort_is_rejected(self) -> None:
        """Changing sort mid-pagination invalidates the cursor.

        Reusing it would compare against the wrong columns and produce a page
        that is neither the next one nor an error.
        """
        issued = encode_cursor(_spec(SortKey("price")), {"price": Decimal("1"), "external_id": 1})

        with pytest.raises(ValidationError) as exc:
            decode_cursor(_spec(SortKey("rating")), issued)

        assert "cursor" in str(exc.value).lower()

    @pytest.mark.parametrize("bad", ["", "not-base64!!", "YWJj", "e30="])
    def test_malformed_cursor_raises_validation_error_not_a_crash(self, bad: str) -> None:
        """A tampered cursor is a client error — 400, never a 500."""
        with pytest.raises(ValidationError):
            decode_cursor(_spec(), bad)


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Row:
    external_id: int
    rating: Decimal
    sale_price: Decimal


class TestPageRequest:
    def test_accepts_the_sizes_the_interface_offers(self) -> None:
        for size in (10, 25, 50, 100):
            assert PageRequest(limit=size).limit == size

    def test_rejects_non_positive_limit(self) -> None:
        with pytest.raises(ValidationError):
            PageRequest(limit=0)

    def test_rejects_limit_above_the_cap(self) -> None:
        """An unbounded page size is a denial-of-service knob for the caller."""
        with pytest.raises(ValidationError):
            PageRequest(limit=MAX_PAGE_SIZE + 1)

    def test_fetch_size_asks_for_one_extra_row(self) -> None:
        """The sentinel row answers `has_next` without a second COUNT(*)."""
        assert PageRequest(limit=50).fetch_size == 51


class TestBuildPage:
    def _rows(self, count: int) -> list[Row]:
        return [
            Row(external_id=i, rating=Decimal("4.0"), sale_price=Decimal(i)) for i in range(count)
        ]

    def test_extra_row_signals_more_and_is_trimmed(self) -> None:
        """The repository fetches limit+1; the extra row answers `has_next`."""
        page = build_page(self._rows(4), spec=_spec(), limit=3)

        assert len(page.items) == 3
        assert page.has_next is True
        assert page.next_cursor is not None

    def test_short_result_means_the_end(self) -> None:
        page = build_page(self._rows(2), spec=_spec(), limit=3)

        assert page.has_next is False
        assert page.next_cursor is None

    def test_exact_fill_without_extra_row_means_the_end(self) -> None:
        page = build_page(self._rows(3), spec=_spec(), limit=3)

        assert page.has_next is False

    def test_empty_result(self) -> None:
        page: Page[Row] = build_page([], spec=_spec(), limit=3)

        assert page.items == () and page.has_next is False and page.next_cursor is None

    def test_reads_sort_values_from_mappings_too(self) -> None:
        """Rows arrive as ORM objects from catalog and as dicts from ClickHouse."""
        rows = [{"external_id": i} for i in range(4)]

        page = build_page(rows, spec=_spec(), limit=3)

        assert page.next_cursor is not None
        assert decode_cursor(_spec(), page.next_cursor)["external_id"] == 2

    def test_cursor_points_at_the_last_returned_row(self) -> None:
        spec = _spec(SortKey("rating", descending=True))
        page = build_page(self._rows(4), spec=spec, limit=3)

        assert page.next_cursor is not None
        assert decode_cursor(spec, page.next_cursor)["external_id"] == 2


# --------------------------------------------------------------------------
# The property that matters
# --------------------------------------------------------------------------

_OPS = {"<": operator.lt, ">": operator.gt, "=": operator.eq}


def _matches(row: dict[str, Any], predicate: tuple[tuple[Comparison, ...], ...]) -> bool:
    """Evaluate the predicate the way a database would: OR of ANDs."""
    return any(
        all(_OPS[c.op](row[c.field], c.value) for c in conjunction) for conjunction in predicate
    )


def _sorted_by(rows: list[dict[str, Any]], spec: SortSpec) -> list[dict[str, Any]]:
    """Independent reference ordering — successive stable sorts, last key first."""
    result = list(rows)
    for key in reversed(spec.all_keys):
        result.sort(key=lambda r, f=key.field: r[f], reverse=key.descending)  # type: ignore[misc]
    return result


_FIELDS = ("rating", "sale_price", "reviews_count")


@st.composite
def _dataset(draw: st.DrawFn) -> tuple[list[dict[str, Any]], SortSpec, int]:
    # Small value ranges on purpose: ties are where keyset pagination breaks,
    # so they must be common in the generated data rather than rare.
    rows = draw(
        st.lists(
            st.fixed_dictionaries(
                {
                    "rating": st.integers(min_value=0, max_value=3),
                    "sale_price": st.integers(min_value=0, max_value=3),
                    "reviews_count": st.integers(min_value=0, max_value=3),
                }
            ),
            min_size=0,
            max_size=25,
        )
    )
    for index, row in enumerate(rows):
        row["external_id"] = index  # unique tiebreaker, as production requires

    chosen = draw(st.lists(st.sampled_from(_FIELDS), min_size=0, max_size=3, unique=True))
    keys = tuple(SortKey(field, descending=draw(st.booleans())) for field in chosen)
    spec = SortSpec(keys=keys, tiebreaker=SortKey("external_id", descending=draw(st.booleans())))

    return rows, spec, draw(st.integers(min_value=1, max_value=5))


@settings(max_examples=300, deadline=None)
@given(_dataset())
def test_paging_visits_every_row_exactly_once(
    dataset: tuple[list[dict[str, Any]], SortSpec, int],
) -> None:
    """Walk the whole set page by page; the concatenation must equal a full sort.

    Covers every direction combination, ties on every level, and page
    boundaries that land inside a run of equal values — the three things that
    break tuple comparison.
    """
    rows, spec, limit = dataset
    expected = _sorted_by(rows, spec)

    visited: list[dict[str, Any]] = []
    cursor_values: dict[str, Any] | None = None

    for _ in range(len(rows) + 2):  # bounded: a bug must fail, not hang
        candidates = _sorted_by(rows, spec)
        if cursor_values is not None:
            predicate = keyset_predicate(spec, cursor_values)
            candidates = [r for r in candidates if _matches(r, predicate)]

        chunk = candidates[:limit]
        if not chunk:
            break

        visited += chunk
        cursor_values = {key.field: chunk[-1][key.field] for key in spec.all_keys}

    assert visited == expected

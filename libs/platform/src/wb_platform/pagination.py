"""Keyset pagination shared by every service (T015).

Replaces ``OFFSET``, which degrades on deep pages because the database counts
and discards every skipped row, and which shifts under concurrent inserts —
the reader silently sees a row twice or not at all.

The hard part is not the cursor. It is that the tuple-comparison shortcut,

    WHERE (sale_price, external_id) > (:sale_price, :external_id)

is correct only while every level sorts the same way, and the product ships a
preset that does not: «Дешевле ↑ + рейтинг ↓». For mixed directions the
comparison must be expanded into a chain of ORed conjunctions
([док. 7, §7.5](../../../../docs/migration/07-implementation-plan.md)), which
is what :func:`keyset_predicate` builds.

**Deliberately free of SQLAlchemy.** The predicate is returned as data, and the
caller renders it — ten lines against SQLAlchemy in catalog, ten more against
raw SQL in analytics, where ClickHouse speaks a different dialect. Binding the
module to one dialect would force a gRPC-free service like api-gateway to carry
a database driver, and would make the whole thing untestable without one. If a
renderer turns out to be copied verbatim into a second service, *that* is when
it moves here.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Final, Literal

from wb_platform.errors import FieldError, ValidationError

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "Comparison",
    "Page",
    "PageRequest",
    "Predicate",
    "SortKey",
    "SortSpec",
    "build_page",
    "decode_cursor",
    "encode_cursor",
    "keyset_predicate",
    "order_by",
]

# Page sizes the interface offers today: 10 / 25 / 50 / 100. The cap is the
# largest of them — an unbounded page size is a denial-of-service knob handed
# to the caller, and the charts no longer need the whole set (отклонение П1).
DEFAULT_PAGE_SIZE: Final = 25
MAX_PAGE_SIZE: Final = 100

_ComparisonOp = Literal["<", ">", "="]

# Cursors are versioned: a future change to the payload shape must invalidate
# outstanding cursors loudly rather than be misread as tampering.
_CURSOR_VERSION: Final = 1
_FINGERPRINT_LENGTH: Final = 12


@dataclass(frozen=True, slots=True)
class SortKey:
    field: str
    descending: bool = False


@dataclass(frozen=True, slots=True)
class Comparison:
    """One term of the keyset predicate: ``field op value``."""

    field: str
    op: _ComparisonOp
    value: Any


# Disjunction of conjunctions: OR over tuples of ANDed comparisons.
Predicate = tuple[tuple[Comparison, ...], ...]


@dataclass(frozen=True, slots=True)
class SortSpec:
    """An ordering plus the unique key that breaks its ties.

    ``tiebreaker`` is a separate field rather than a convention about the last
    element of ``keys``: without a unique final key, rows sharing every sorted
    value order differently between queries, and pagination starts skipping or
    repeating them. Making it a distinct argument means it cannot be forgotten.
    """

    keys: tuple[SortKey, ...]
    tiebreaker: SortKey

    def __post_init__(self) -> None:
        fields = [key.field for key in self.keys]
        duplicates = {field for field in fields if fields.count(field) > 1}
        if duplicates:
            raise ValidationError(
                f"Sort field repeated: {', '.join(sorted(duplicates))}.",
                details=[FieldError(field=field, code="duplicate") for field in sorted(duplicates)],
            )
        if self.tiebreaker.field in fields:
            raise ValidationError(
                f"Sort field {self.tiebreaker.field!r} is reserved as the tiebreaker.",
                details=[FieldError(field=self.tiebreaker.field, code="reserved")],
            )

    @property
    def all_keys(self) -> tuple[SortKey, ...]:
        """Sort keys with the tiebreaker appended — the actual ordering."""
        return (*self.keys, self.tiebreaker)

    def fingerprint(self) -> str:
        """Short digest of the ordering, embedded in cursors issued for it.

        Lets :func:`decode_cursor` reject a cursor whose sort has changed,
        which would otherwise compare against the wrong columns and return a
        page that is neither the next one nor an error.
        """
        material = "|".join(f"{key.field}:{int(key.descending)}" for key in self.all_keys)
        digest = hashlib.sha256(material.encode()).hexdigest()
        return digest[:_FINGERPRINT_LENGTH]


def order_by(spec: SortSpec) -> tuple[tuple[str, bool], ...]:
    """``(field, descending)`` pairs for the query's ORDER BY, tiebreaker last."""
    return tuple((key.field, key.descending) for key in spec.all_keys)


def keyset_predicate(spec: SortSpec, cursor_values: dict[str, Any]) -> Predicate:
    """Build the "strictly after the cursor" condition for ``spec``.

    For keys ``(k1 d1, k2 d2, k3 d3)`` and cursor ``(v1, v2, v3)``::

        (k1 OP1 v1)
        OR (k1 = v1 AND k2 OP2 v2)
        OR (k1 = v1 AND k2 = v2 AND k3 OP3 v3)

    where ``OPi`` is ``<`` for a descending level and ``>`` for an ascending
    one. Correct for any mix of directions, unlike tuple comparison.
    """
    keys = spec.all_keys
    _require_complete_cursor(keys, cursor_values)

    conjunctions: list[tuple[Comparison, ...]] = []
    for index, key in enumerate(keys):
        equalities = tuple(
            Comparison(prev.field, "=", cursor_values[prev.field]) for prev in keys[:index]
        )
        op: _ComparisonOp = "<" if key.descending else ">"
        conjunctions.append((*equalities, Comparison(key.field, op, cursor_values[key.field])))

    return tuple(conjunctions)


def _require_complete_cursor(keys: Sequence[SortKey], values: dict[str, Any]) -> None:
    """Every sorted column needs a non-NULL cursor value.

    NULL is refused rather than handled: ``NULL < x`` evaluates to NULL, so a
    nullable sort column silently drops rows from the page instead of failing.
    A short page nobody notices is worse than an error.
    """
    missing = [key.field for key in keys if key.field not in values]
    if missing:
        raise ValidationError(
            "Cursor is missing values for sorted columns.",
            details=[FieldError(field=field, code="missing") for field in missing],
        )

    null_valued = [key.field for key in keys if values[key.field] is None]
    if null_valued:
        raise ValidationError(
            "Keyset pagination requires non-nullable sort columns; "
            f"got NULL for: {', '.join(null_valued)}.",
            details=[FieldError(field=field, code="null_not_allowed") for field in null_valued],
        )


# --------------------------------------------------------------------------
# Cursor encoding
# --------------------------------------------------------------------------

# JSON has no Decimal, datetime or date. Each value is tagged so the exact type
# comes back: money round-tripped through float would drift, and it is money.
_TAG_BY_TYPE: Final[dict[type, str]] = {
    bool: "b",
    int: "i",
    float: "f",
    str: "s",
    Decimal: "d",
    datetime: "dt",
    date: "date",
}


def _tag(value: Any) -> tuple[str, str]:
    # bool before int: bool is a subclass of int, and `type(True) is int` is
    # False but an isinstance chain would mislabel it.
    tag = _TAG_BY_TYPE.get(type(value))
    if tag is None:
        raise ValidationError(f"Cannot put {type(value).__name__} in a cursor.")
    return tag, value.isoformat() if isinstance(value, (datetime, date)) else str(value)


def _untag(tag: str, raw: str) -> Any:
    match tag:
        case "b":
            return raw == "True"
        case "i":
            return int(raw)
        case "f":
            return float(raw)
        case "s":
            return raw
        case "d":
            return Decimal(raw)
        case "dt":
            return datetime.fromisoformat(raw)
        case "date":
            return date.fromisoformat(raw)
        case _:
            raise ValidationError("Malformed cursor.")


def encode_cursor(spec: SortSpec, values: dict[str, Any]) -> str:
    """Encode cursor values as an opaque, URL-safe string.

    Opaque on purpose: a readable cursor invites clients to construct their
    own, which turns an internal detail into a contract we would have to keep.
    """
    payload = {
        "v": _CURSOR_VERSION,
        "f": spec.fingerprint(),
        "k": [[key.field, *_tag(values[key.field])] for key in spec.all_keys],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(spec: SortSpec, cursor: str) -> dict[str, Any]:
    """Decode a cursor issued for ``spec``.

    Every failure — malformed, truncated, tampered with, or issued for a
    different ordering — surfaces as :class:`ValidationError`, so the edge
    answers 400 rather than 500.
    """
    payload = _decode_payload(cursor)

    if payload.get("v") != _CURSOR_VERSION:
        raise ValidationError("Cursor was issued by an incompatible version.")
    if payload.get("f") != spec.fingerprint():
        raise ValidationError("Cursor does not match the requested sort order.")

    entries = payload.get("k")
    if not isinstance(entries, list):
        raise ValidationError("Malformed cursor.")

    values: dict[str, Any] = {}
    for entry in entries:
        match entry:
            case [str(field), str(tag), str(raw)]:
                values[field] = _untag(tag, raw)
            case _:
                raise ValidationError("Malformed cursor.")

    _require_complete_cursor(spec.all_keys, values)
    return values


def _decode_payload(cursor: str) -> dict[str, Any]:
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode())
        payload = json.loads(raw)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValidationError("Malformed cursor.") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Malformed cursor.")
    return payload


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PageRequest:
    """A validated page size plus the cursor the client came back with."""

    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValidationError(
                "limit must be >= 1.", details=[FieldError(field="limit", code="too_small")]
            )
        if self.limit > MAX_PAGE_SIZE:
            raise ValidationError(
                f"limit must be <= {MAX_PAGE_SIZE}.",
                details=[FieldError(field="limit", code="too_large")],
            )

    @property
    def fetch_size(self) -> int:
        """Rows to ask the database for: one extra answers ``has_next``.

        Cheaper than a second ``COUNT(*)``, which on a filtered set costs about
        as much as the page itself.
        """
        return self.limit + 1


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: tuple[T, ...]
    next_cursor: str | None

    @property
    def has_next(self) -> bool:
        return self.next_cursor is not None


def build_page[T](rows: Sequence[T], *, spec: SortSpec, limit: int) -> Page[T]:
    """Trim the sentinel row and issue the cursor for the next page.

    ``rows`` is what the repository fetched with ``PageRequest.fetch_size``:
    at most ``limit + 1`` items. Receiving the extra one is the signal that a
    next page exists.
    """
    has_next = len(rows) > limit
    items = tuple(rows[:limit])

    if not has_next or not items:
        return Page(items=items, next_cursor=None)

    last = items[-1]
    values = {key.field: _read(last, key.field) for key in spec.all_keys}
    return Page(items=items, next_cursor=encode_cursor(spec, values))


def _read(row: Any, field: str) -> Any:
    """Read a sort field from a row — an ORM object, a dataclass or a mapping."""
    if isinstance(row, dict):
        return row[field]
    return getattr(row, field)

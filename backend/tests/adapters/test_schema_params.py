"""The schema describes the parameters the parsers actually read (T047).

``parse_product_filter`` and ``parse_ordering`` pull keys out of the request
dictionary by hand, and ``@extend_schema`` declares them separately. Nothing in
Python connects the two, so they drift at the first edit — and the drift is
silent: the schema still validates, it just describes a different API than the
one running. A client generated from it then omits a filter that works, or
sends one that is ignored.

This reads the parser's source and compares the keys it looks up against the
declared list. Source inspection rather than calling the parser: a parameter
that is read but never declared cannot be discovered by passing values in,
because the parser accepts anything and silently ignores what it does not know.
"""

from __future__ import annotations

import ast
import inspect

from catalog.adapters.inbound.http import request_filters
from catalog.adapters.inbound.http.schema_params import (
    DECLARED_PARAM_NAMES,
    FILTER_PARAM_NAMES,
    ORDERING_PARAM_NAMES,
    PAGINATION_PARAMETERS,
    PRODUCT_LIST_PARAMETERS,
)


def _looked_up_keys(function: object) -> set[str]:
    """String literals passed to `params.get(...)` or `params.getlist(...)`.

    Also picks up the `key` argument of the module's `_decimal`/`_int`
    helpers, which is how most parameters are actually read.
    """
    tree = ast.parse(inspect.getsource(function))  # type: ignore[arg-type]
    keys: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # params.get("min_price") / params.getlist("query")
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "getlist"}:
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    keys.add(argument.value)

        # _decimal(params, "min_price") — second positional argument
        if isinstance(node.func, ast.Name) and node.func.id in {"_decimal", "_int"}:
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                value = node.args[1].value
                if isinstance(value, str):
                    keys.add(value)

    return keys


class TestNoDrift:
    def test_every_filter_key_the_parser_reads_is_declared(self) -> None:
        read = _looked_up_keys(request_filters.parse_product_filter)

        assert read <= DECLARED_PARAM_NAMES, f"undeclared filter parameters: {read - DECLARED_PARAM_NAMES}"

    def test_every_declared_filter_is_actually_read(self) -> None:
        """The other direction: a documented parameter that does nothing is a
        lie the schema tells every client generated from it."""
        read = _looked_up_keys(request_filters.parse_product_filter)

        assert FILTER_PARAM_NAMES <= read, f"declared but ignored: {FILTER_PARAM_NAMES - read}"

    def test_ordering_parameter_matches(self) -> None:
        read = _looked_up_keys(request_filters.parse_ordering)

        assert ORDERING_PARAM_NAMES <= read

    def test_the_extractor_can_actually_find_keys(self) -> None:
        """Guards the guard.

        A drift test whose extractor returns an empty set passes forever while
        checking nothing — the exact failure mode it exists to prevent.
        """
        assert "min_price" in _looked_up_keys(request_filters.parse_product_filter)


class TestDeclarations:
    def test_the_list_endpoint_declares_filters_ordering_and_pagination(self) -> None:
        names = {parameter.name for parameter in PRODUCT_LIST_PARAMETERS}

        assert names == DECLARED_PARAM_NAMES

    def test_ordering_enumerates_both_directions(self) -> None:
        """A client should not have to learn the '-' prefix from prose."""
        (ordering,) = [p for p in PRODUCT_LIST_PARAMETERS if p.name == "ordering"]

        assert "reviews_count" in ordering.enum
        assert "-reviews_count" in ordering.enum

    def test_page_size_cap_is_documented(self) -> None:
        """1000 is not a round number a client would guess, and exceeding it
        silently truncates."""
        (page_size,) = [p for p in PAGINATION_PARAMETERS if p.name == "page_size"]

        assert "1000" in page_size.description

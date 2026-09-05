"""Schema generation hooks (framework glue).

`config.urls` mounts every context twice — under `api/` and under its `v1/`
alias — so endpoint collection sees each operation twice and drf-spectacular
resolves the duplicate `operationId`s with numeral suffixes: `products_list`
and `products_list_2`. That is not a warning to silence. A generated client
would carry both, and `contracts/openapi/v1.yaml` is the frozen reference the
whole migration is checked against.

The contract describes one prefix, and it is `/api/` — the surface Django
actually shipped. `/v1/` is a routing alias added for the cutover, not a second
API, and the paths it will eventually serve are not all the same ones
(`/api/parse/` becomes `/v1/collections`, see док. 2, §2.2).
"""

from __future__ import annotations

from typing import Any

#: Prefixes the schema does not describe. Aliases only — never a real endpoint.
_ALIAS_PREFIXES = ("/v1/",)


Endpoint = tuple[str, Any, str, Any]


def exclude_alias_prefixes(endpoints: list[Endpoint]) -> list[Endpoint]:
    """Drop the alias mounts, keeping one entry per operation."""
    return [e for e in endpoints if not e[0].startswith(_ALIAS_PREFIXES)]

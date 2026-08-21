"""Accounts application DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SavedSearch:
    """A user's named search (query + filters), owner-scoped (FE-09)."""

    id: int
    owner_id: int
    name: str
    query: str
    filters: dict = field(default_factory=dict)

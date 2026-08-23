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


@dataclass(frozen=True)
class VerifiedIdentity:
    """A validated external identity (e.g. a Google account), provider-agnostic."""

    provider: str
    external_id: str
    email: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class AuthenticatedUser:
    """A local account resolved from a credential; `created` flags a fresh signup."""

    id: int
    username: str
    email: str | None = None
    providers: tuple[str, ...] = ()
    created: bool = False

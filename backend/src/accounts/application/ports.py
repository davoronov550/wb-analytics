"""Accounts outbound ports."""

from __future__ import annotations

from typing import Protocol

from accounts.application.dto import AuthenticatedUser, SavedSearch, VerifiedIdentity

__all__ = ["SavedSearchRepositoryPort", "IdentityVerifierPort", "UserDirectoryPort"]


class IdentityVerifierPort(Protocol):
    def verify(self, credential: str) -> VerifiedIdentity | None:
        """Verify an external credential (e.g. a Google ID token).

        Returns the identity it attests to, or None if the credential is
        invalid/untrusted. Must not raise on a merely-invalid token.
        """
        ...


class UserDirectoryPort(Protocol):
    def find_or_create_by_identity(self, identity: VerifiedIdentity) -> AuthenticatedUser:
        """Resolve a local account for an external identity, provisioning one if
        needed, and return it (with `created` set when a new account was made)."""
        ...


class SavedSearchRepositoryPort(Protocol):
    def create(self, *, owner_id: int, name: str, query: str, filters: dict) -> SavedSearch: ...

    def list(self, owner_id: int) -> list[SavedSearch]: ...

    def get(self, owner_id: int, saved_id: int) -> SavedSearch | None:
        """Owner-scoped lookup (None if missing or owned by someone else)."""
        ...

    def delete(self, owner_id: int, saved_id: int) -> bool:
        """Delete if owned by ``owner_id``; return whether a row was removed."""
        ...

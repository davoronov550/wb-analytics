"""Authenticate a user via an external identity provider (e.g. Google).

Pure orchestration: verify the credential through a port, then resolve/provision
a local account through another. No framework or provider knowledge here.
"""

from __future__ import annotations

from accounts.application.dto import AuthenticatedUser
from accounts.application.errors import InvalidCredential
from accounts.application.ports import IdentityVerifierPort, UserDirectoryPort


class AuthenticateWithProvider:
    def __init__(self, *, verifier: IdentityVerifierPort, directory: UserDirectoryPort) -> None:
        self._verifier = verifier
        self._directory = directory

    def execute(self, credential: str) -> AuthenticatedUser:
        identity = self._verifier.verify(credential)
        if identity is None:
            raise InvalidCredential("credential could not be verified")
        return self._directory.find_or_create_by_identity(identity)

"""AuthenticateWithProvider use-case tests — fakes, no DB, no network."""

import pytest

from accounts.application.dto import AuthenticatedUser, VerifiedIdentity
from accounts.application.errors import InvalidCredential
from accounts.application.use_cases.authenticate_with_provider import AuthenticateWithProvider


class FakeVerifier:
    def __init__(self, identity: VerifiedIdentity | None):
        self._identity = identity
        self.seen: list[str] = []

    def verify(self, credential: str) -> VerifiedIdentity | None:
        self.seen.append(credential)
        return self._identity


class FakeDirectory:
    def __init__(self):
        self.calls: list[VerifiedIdentity] = []

    def find_or_create_by_identity(self, identity: VerifiedIdentity) -> AuthenticatedUser:
        self.calls.append(identity)
        return AuthenticatedUser(
            id=42, username="jane", email=identity.email, providers=("google",), created=True
        )


def test_verifies_then_resolves_account():
    identity = VerifiedIdentity(provider="google", external_id="sub-1", email="j@x.io", name="Jane")
    verifier, directory = FakeVerifier(identity), FakeDirectory()

    account = AuthenticateWithProvider(verifier=verifier, directory=directory).execute("tok")

    assert verifier.seen == ["tok"]
    assert directory.calls == [identity]
    assert account.id == 42
    assert account.created is True


def test_raises_on_invalid_credential_and_never_touches_directory():
    verifier, directory = FakeVerifier(None), FakeDirectory()

    with pytest.raises(InvalidCredential):
        AuthenticateWithProvider(verifier=verifier, directory=directory).execute("bad")

    assert directory.calls == []

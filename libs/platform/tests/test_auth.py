"""Tests for access-token verification (T020).

The contract under test: rotating a signing key does not invalidate tokens
already issued under the previous one.

That is the failure this module is built around. Replacing the cached key set
on every JWKS fetch is the obvious implementation and it logs out every user
holding an outgoing-key token — mid-session, for no reason the operator can
see, because nothing errors.
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from wb_platform.auth import AccessToken, JwksClient, TokenVerifier
from wb_platform.errors import UnauthenticatedError

ISSUER = "https://identity.wb-analytics.internal"
AUDIENCE = "wb-analytics"


def _keypair() -> tuple[Any, dict[str, Any]]:
    """A private key plus its public half in JWKS form."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()

    def b64(value: int) -> str:
        import base64

        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return private, {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "n": b64(numbers.n),
        "e": b64(numbers.e),
    }


KEY_A, JWK_A = _keypair()
KEY_B, JWK_B = _keypair()
JWK_A = {**JWK_A, "kid": "key-a"}
JWK_B = {**JWK_B, "kid": "key-b"}


def issue(
    key: Any = KEY_A,
    kid: str = "key-a",
    *,
    subject: str = "42",
    lifetime: int = 300,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    scope: str = "catalog:read",
    omit: str | None = None,
) -> str:
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + lifetime,
        "iat": int(time.time()),
        "scope": scope,
    }
    if omit:
        claims.pop(omit, None)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


class _Jwks:
    """A JWKS endpoint whose contents the test controls."""

    def __init__(self, *keys: dict[str, Any]) -> None:
        self.keys = list(keys)
        self.calls = 0

    async def __call__(self) -> dict[str, Any]:
        self.calls += 1
        return {"keys": self.keys}


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _verifier(fetcher: _Jwks, clock: _Clock | None = None) -> TokenVerifier:
    jwks = JwksClient(fetcher, clock=clock or _Clock())
    return TokenVerifier(jwks, issuer=ISSUER, audience=AUDIENCE)


class TestValidToken:
    @pytest.mark.asyncio
    async def test_accepts_a_well_formed_token(self) -> None:
        token = await _verifier(_Jwks(JWK_A)).verify(issue())

        assert isinstance(token, AccessToken)
        assert token.subject == "42"
        assert token.owner_id == 42

    @pytest.mark.asyncio
    async def test_scopes_are_parsed_from_the_space_delimited_claim(self) -> None:
        token = await _verifier(_Jwks(JWK_A)).verify(issue(scope="catalog:read export:write"))

        assert token.scopes == {"catalog:read", "export:write"}

    @pytest.mark.asyncio
    async def test_non_numeric_subject_is_rejected_when_used_as_owner_id(self) -> None:
        token = await _verifier(_Jwks(JWK_A)).verify(issue(subject="not-a-number"))

        with pytest.raises(UnauthenticatedError):
            _ = token.owner_id


class TestKeyRotation:
    """The property this module exists for."""

    @pytest.mark.asyncio
    async def test_tokens_from_the_previous_key_survive_a_rotation(self) -> None:
        """Merged, not replaced.

        Replacing the cache would reject every outstanding token signed with
        the outgoing key — logging out every active user the moment identity
        rotates, with nothing in the logs to explain it.
        """
        fetcher = _Jwks(JWK_A)
        clock = _Clock()
        verifier = _verifier(fetcher, clock)
        old_token = issue(KEY_A, "key-a")
        await verifier.verify(old_token)

        # identity-service rotates: JWKS now advertises only the new key.
        fetcher.keys = [JWK_B]
        clock.advance(700)  # cache expires

        assert (await verifier.verify(issue(KEY_B, "key-b"))).subject == "42"
        assert (await verifier.verify(old_token)).subject == "42"

    @pytest.mark.asyncio
    async def test_unknown_kid_triggers_exactly_one_refresh(self) -> None:
        fetcher = _Jwks(JWK_A)
        verifier = _verifier(fetcher)
        await verifier.verify(issue())
        before = fetcher.calls

        fetcher.keys = [JWK_A, JWK_B]
        await verifier.verify(issue(KEY_B, "key-b"))

        assert fetcher.calls == before + 1

    @pytest.mark.asyncio
    async def test_forged_kids_do_not_hammer_identity_service(self) -> None:
        """A stream of unknown key ids must not become a denial-of-service."""
        fetcher = _Jwks(JWK_A)
        clock = _Clock()
        verifier = _verifier(fetcher, clock)
        await verifier.verify(issue())
        before = fetcher.calls

        for _ in range(50):
            with pytest.raises(UnauthenticatedError):
                await verifier.verify(issue(KEY_B, "forged"))
            clock.advance(5)  # well past the inter-fetch floor

        assert fetcher.calls - before == 1  # the negative cache, not a cooldown

    @pytest.mark.asyncio
    async def test_cached_keys_are_not_refetched_on_every_request(self) -> None:
        fetcher = _Jwks(JWK_A)
        verifier = _verifier(fetcher)

        for _ in range(5):
            await verifier.verify(issue())

        assert fetcher.calls == 1


class TestRejection:
    @pytest.mark.asyncio
    async def test_expired_token(self) -> None:
        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(issue(lifetime=-60))

    @pytest.mark.asyncio
    async def test_signature_from_a_key_that_is_not_advertised(self) -> None:
        """A token signed with key B but claiming key A's id."""
        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(issue(KEY_B, "key-a"))

    @pytest.mark.asyncio
    async def test_wrong_issuer(self) -> None:
        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(issue(issuer="https://evil.example"))

    @pytest.mark.asyncio
    async def test_wrong_audience(self) -> None:
        """A token minted for another service must not be accepted here."""
        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(issue(audience="other-app"))

    @pytest.mark.asyncio
    async def test_token_without_a_key_id(self) -> None:
        token = jwt.encode({"sub": "1"}, KEY_A, algorithm="RS256")

        with pytest.raises(UnauthenticatedError, match="key id"):
            await _verifier(_Jwks(JWK_A)).verify(token)

    @pytest.mark.asyncio
    async def test_malformed_token(self) -> None:
        with pytest.raises(UnauthenticatedError, match="malformed"):
            await _verifier(_Jwks(JWK_A)).verify("not.a.token")

    @pytest.mark.parametrize("missing", ["exp", "sub", "iss", "aud"])
    @pytest.mark.asyncio
    async def test_required_claims_are_enforced(self, missing: str) -> None:
        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(issue(omit=missing))

    @pytest.mark.asyncio
    async def test_algorithm_none_is_refused(self) -> None:
        """Algorithm confusion: the header must never choose the algorithm."""
        forged = jwt.encode(
            {"sub": "42", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 300},
            key="",
            algorithm="none",
            headers={"kid": "key-a"},
        )

        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(forged)

    @pytest.mark.asyncio
    async def test_hmac_signed_with_the_public_key_is_refused(self) -> None:
        """The classic RS256 → HS256 downgrade, using the public key as secret.

        Assembled by hand: PyJWT refuses to *encode* a PEM key as an HMAC
        secret, so building the forgery through it would test PyJWT's encoder
        rather than our decoder. The defence under test is passing an explicit
        algorithm list to `decode`, never the one named in the header.
        """
        import base64
        import hashlib
        import hmac
        import json as _json

        from cryptography.hazmat.primitives import serialization

        public_pem = KEY_A.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        def segment(payload: dict[str, Any]) -> bytes:
            raw = _json.dumps(payload, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).rstrip(b"=")

        signing_input = b".".join(
            (
                segment({"alg": "HS256", "typ": "JWT", "kid": "key-a"}),
                segment(
                    {
                        "sub": "42",
                        "iss": ISSUER,
                        "aud": AUDIENCE,
                        "exp": int(time.time()) + 300,
                    }
                ),
            )
        )
        signature = base64.urlsafe_b64encode(
            hmac.new(public_pem, signing_input, hashlib.sha256).digest()
        ).rstrip(b"=")
        forged = (signing_input + b"." + signature).decode()

        with pytest.raises(UnauthenticatedError):
            await _verifier(_Jwks(JWK_A)).verify(forged)


class TestErrorDisclosure:
    @pytest.mark.asyncio
    async def test_failures_do_not_say_which_check_failed(self) -> None:
        """Telling an attacker whether the signature or the expiry failed
        tells them which half of a forgery is already working."""
        messages = set()
        for token in (issue(lifetime=-60), issue(KEY_B, "key-a"), issue(issuer="https://evil")):
            with pytest.raises(UnauthenticatedError) as exc:
                await _verifier(_Jwks(JWK_A)).verify(token)
            messages.add(exc.value.message)

        assert messages == {"Token is not valid."}

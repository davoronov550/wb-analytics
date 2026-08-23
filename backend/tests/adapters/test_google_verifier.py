"""GoogleIdentityVerifier tests — offline via an injected verify function."""

from accounts.adapters.outbound.identity.google import GoogleIdentityVerifier


def test_maps_google_claims_to_identity():
    claims = {"sub": "1234567890", "email": "a@b.io", "email_verified": True, "name": "Ann"}
    verifier = GoogleIdentityVerifier(client_id="cid", verify_fn=lambda _t: claims)

    identity = verifier.verify("token")

    assert identity is not None
    assert identity.provider == "google"
    assert identity.external_id == "1234567890"
    assert identity.email == "a@b.io"
    assert identity.name == "Ann"


def test_drops_unverified_email():
    claims = {"sub": "x", "email": "spoof@b.io", "email_verified": False}
    verifier = GoogleIdentityVerifier(client_id="cid", verify_fn=lambda _t: claims)

    identity = verifier.verify("token")

    assert identity is not None
    assert identity.email is None


def test_returns_none_when_verification_raises():
    def boom(_token: str) -> dict:
        raise ValueError("bad audience")

    verifier = GoogleIdentityVerifier(client_id="cid", verify_fn=boom)
    assert verifier.verify("token") is None


def test_returns_none_without_client_id_or_token():
    verifier = GoogleIdentityVerifier(client_id="", verify_fn=lambda _t: {"sub": "x"})
    assert verifier.verify("token") is None
    assert GoogleIdentityVerifier(client_id="cid", verify_fn=lambda _t: {"sub": "x"}).verify("") is None

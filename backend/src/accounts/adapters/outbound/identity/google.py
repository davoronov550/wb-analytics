"""Google ID-token verifier (outbound adapter for IdentityVerifierPort).

Wraps google-auth. The verification callable is injectable so the use case and
HTTP layers can be tested offline with a fake, keeping tests deterministic
.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from accounts.application.dto import VerifiedIdentity

logger = logging.getLogger("accounts")

VerifyFn = Callable[[str], dict]


class GoogleIdentityVerifier:
    provider = "google"

    def __init__(self, *, client_id: str, verify_fn: VerifyFn | None = None) -> None:
        self._client_id = client_id
        self._verify_fn = verify_fn or self._default_verify

    def _default_verify(self, credential: str) -> dict:
        # Imported lazily so the module (and tests using an injected verify_fn)
        # don't require google-auth's HTTP transport / the `requests` package.
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        return google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), self._client_id
        )

    def verify(self, credential: str) -> VerifiedIdentity | None:
        if not credential or not self._client_id:
            return None
        try:
            claims = self._verify_fn(credential)
        except Exception as exc:  # invalid signature / audience / expiry, etc.
            logger.info("google id_token verification failed: %s", exc)
            return None
        sub = claims.get("sub")
        if not sub:
            return None
        # google-auth validates iss/aud/exp; we additionally require a verified email.
        email = claims.get("email") if claims.get("email_verified", True) else None
        return VerifiedIdentity(
            provider=self.provider,
            external_id=str(sub),
            email=email,
            name=claims.get("name"),
        )

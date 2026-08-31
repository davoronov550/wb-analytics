"""Access-token verification shared by every service (T020).

RS256, not HS256. A shared secret would have to be distributed to all nine
services, and any one of them could then *mint* tokens, not merely check them.
With asymmetric signing only ``identity-service`` holds the private key; the
rest verify against a published JWKS and can do nothing else.

That also removes the database from the hot path. Today every request is
verified by SimpleJWT and every refresh reads ``token_blacklist``; here
verification is a signature check against a cached key, and only refresh
consults the revocation list.

**The rotation rule this module exists to hold.** When a key rotates, tokens
signed with the previous one stay valid until they expire — a few minutes
later. Fetching JWKS and replacing the cache wholesale would reject them all
at once and log out every user mid-session, which is why keys are *merged* by
``kid`` and an unknown ``kid`` triggers exactly one refresh.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

import jwt
from jwt import PyJWK, PyJWTError

from wb_platform.errors import UnauthenticatedError

__all__ = [
    "AccessToken",
    "JwksClient",
    "JwksFetcher",
    "TokenVerifier",
]

_ALGORITHM: Final = "RS256"

# How long a fetched key set is trusted before a background refresh. Short
# enough that a revoked key leaves circulation quickly, long enough that JWKS
# is not on the request path.
_DEFAULT_CACHE_SECONDS: Final = 600

# Floor between JWKS fetches. Deliberately short: a longer cooldown would also
# delay the *legitimate* refresh that follows a key rotation, rejecting freshly
# issued tokens for the length of the window. Repeated forgeries are made cheap
# by the negative cache instead, not by making everyone wait.
_MIN_REFRESH_INTERVAL: Final = 1.0


@dataclass(frozen=True, slots=True)
class AccessToken:
    """The claims a service is allowed to act on."""

    subject: str
    expires_at: int
    scopes: frozenset[str] = field(default_factory=frozenset)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def owner_id(self) -> int:
        """``sub`` as the numeric owner id the repositories filter by."""
        try:
            return int(self.subject)
        except ValueError as exc:
            raise UnauthenticatedError("Token subject is not a user id.") from exc


class JwksFetcher(Protocol):
    """Fetches the signing key set from identity-service."""

    async def __call__(self) -> dict[str, Any]: ...


class JwksClient:
    """Caches JWKS and merges rotations instead of replacing them.

    Merging is the whole point. Replacing the cache on every fetch would
    invalidate tokens signed with the outgoing key the moment a new one
    appears, logging out everyone holding one — even though those tokens are
    still within their lifetime.
    """

    def __init__(
        self,
        fetch: JwksFetcher,
        *,
        cache_seconds: int = _DEFAULT_CACHE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._keys: dict[str, PyJWK] = {}
        # Key ids we already fetched for and still did not find. A forged token
        # replayed a thousand times must cost one fetch, not a thousand.
        self._known_absent: set[str] = set()
        self._fetched_at: float | None = None
        # Only the unknown-kid path is throttled, so it keeps its own clock.
        # Sharing one with the staleness refresh made a routine refresh block
        # the very next unknown-kid lookup.
        self._last_unknown_attempt: float | None = None

    async def get(self, kid: str) -> PyJWK:
        """Return the key for ``kid``, refreshing once if it is unknown.

        Two independent reasons to refresh, and they must not share a rate
        limit. Staleness happens at most once per cache window and is never
        throttled. An unknown ``kid`` is the one an attacker can trigger at
        will, so *that* path is bounded — but only from the second distinct
        unknown id onward, because throttling the first would also delay the
        legitimate refresh that follows a key rotation.
        """
        if self._is_stale():
            await self._refresh()

        if kid in self._keys:
            return self._keys[kid]

        if kid not in self._known_absent and self._may_refresh_for_unknown_kid():
            self._last_unknown_attempt = self._clock()
            await self._refresh()

        key = self._keys.get(kid)
        if key is None:
            self._known_absent.add(kid)
            raise UnauthenticatedError("Token was signed with an unknown key.")
        return key

    def _is_stale(self) -> bool:
        return self._fetched_at is None or (self._clock() - self._fetched_at >= self._cache_seconds)

    def _may_refresh_for_unknown_kid(self) -> bool:
        """Allow the first one outright, then at most one per window.

        Repeats of the *same* forged id never reach here — the negative cache
        answers them. This bounds an attacker who varies the id on every
        request, which is the only way to keep forcing fetches.
        """
        if self._last_unknown_attempt is None:
            return True
        return self._clock() - self._last_unknown_attempt >= _MIN_REFRESH_INTERVAL

    async def _refresh(self) -> None:
        now = self._clock()
        document = await self._fetch()
        for entry in document.get("keys", []):
            kid = entry.get("kid")
            if kid:
                # Merged, not replaced — the outgoing key stays usable until
                # the tokens it signed expire on their own.
                self._keys[kid] = PyJWK.from_dict(entry, algorithm=_ALGORITHM)
        # A rotation may have introduced a key previously seen as absent.
        self._known_absent.clear()
        self._fetched_at = now


class TokenVerifier:
    """Verifies access tokens against the published key set."""

    def __init__(
        self,
        jwks: JwksClient,
        *,
        issuer: str,
        audience: str,
        leeway_seconds: int = 5,
    ) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audience = audience
        self._leeway = leeway_seconds

    async def verify(self, token: str) -> AccessToken:
        """Validate signature, expiry, issuer and audience.

        Every failure surfaces as :class:`UnauthenticatedError` with a fixed
        message. Distinguishing "expired" from "bad signature" for the caller
        tells an attacker which half of a forgery worked.
        """
        try:
            header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise UnauthenticatedError("Token is malformed.") from exc

        kid = header.get("kid")
        if not kid:
            raise UnauthenticatedError("Token has no key id.")

        key = await self._jwks.get(kid)

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[_ALGORITHM],  # never from the header — that is alg confusion
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        except PyJWTError as exc:
            raise UnauthenticatedError(
                "Token is not valid.", context={"cause": type(exc).__name__}
            ) from exc

        scope = claims.get("scope", "")
        return AccessToken(
            subject=str(claims["sub"]),
            expires_at=int(claims["exp"]),
            scopes=frozenset(scope.split()) if isinstance(scope, str) else frozenset(scope),
            raw=claims,
        )

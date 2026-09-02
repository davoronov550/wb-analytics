"""Rate-limited auth entry points (inbound adapter).

Every endpoint that accepts a credential guess is throttled under the shared
`auth` scope. `TokenObtainPairView` ships with simplejwt, so the only way to
attach a throttle to the login endpoint is to subclass it.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from catalog.adapters.inbound.http.serializers import VALIDATION_ERROR_SCHEMA, ErrorSerializer

# These two views come from simplejwt, so their schema is whatever the
# integration infers — which is the 200 and nothing else. Both answer 400 on a
# malformed body, 401 on a rejected credential and 429 once the throttle above
# bites, and a contract test reads every one of those as an undocumented
# status until it is written down here.
#
# `extend_schema_view` rather than a decorator on the class: `@extend_schema`
# applied to a view class is silently ignored, and the schema it was meant to
# produce simply never appears.
_CREDENTIAL_EXCHANGE_ERRORS = {
    # simplejwt validates through a serializer, so a malformed body comes back
    # field-keyed rather than as `detail`.
    400: VALIDATION_ERROR_SCHEMA,
    401: ErrorSerializer,
    429: ErrorSerializer,
}


@extend_schema_view(
    post=extend_schema(
        operation_id="auth_login",
        summary="Exchange username and password for a token pair",
        responses={200: TokenObtainPairView.serializer_class, **_CREDENTIAL_EXCHANGE_ERRORS},
    )
)
class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Login. Unthrottled, this accepted unlimited password guesses."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


@extend_schema_view(
    post=extend_schema(
        operation_id="auth_refresh",
        summary="Exchange a refresh token for a new access token",
        responses={200: TokenRefreshView.serializer_class, **_CREDENTIAL_EXCHANGE_ERRORS},
    )
)
class ThrottledTokenRefreshView(TokenRefreshView):
    """Refresh. Also a credential exchange, so it shares the same budget."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

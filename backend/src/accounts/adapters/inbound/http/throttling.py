"""Rate-limited auth entry points (inbound adapter).

Every endpoint that accepts a credential guess is throttled under the shared
`auth` scope. `TokenObtainPairView` ships with simplejwt, so the only way to
attach a throttle to the login endpoint is to subclass it.
"""

from __future__ import annotations

from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Login. Unthrottled, this accepted unlimited password guesses."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class ThrottledTokenRefreshView(TokenRefreshView):
    """Refresh. Also a credential exchange, so it shares the same budget."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

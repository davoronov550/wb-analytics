"""Django implementation of UserDirectoryPort (outbound adapter).

Resolves a local Django user for a verified external identity: reuses the linked
account, links to an existing user with the same email, or provisions a new
password-less account. All ORM knowledge stays here.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.adapters.outbound.persistence.models import ExternalIdentityModel
from accounts.application.dto import AuthenticatedUser, VerifiedIdentity

User = get_user_model()


def _providers_for(user) -> tuple[str, ...]:
    ordered: list[str] = ["password"] if user.has_usable_password() else []
    for provider in (
        ExternalIdentityModel.objects.filter(user=user)
        .values_list("provider", flat=True)
        .distinct()
    ):
        if provider not in ordered:
            ordered.append(provider)
    return tuple(ordered)


def _to_dto(user, *, created: bool) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        email=user.email or None,
        providers=_providers_for(user),
        created=created,
    )


class DjangoUserDirectory:
    @transaction.atomic
    def find_or_create_by_identity(self, identity: VerifiedIdentity) -> AuthenticatedUser:
        link = (
            ExternalIdentityModel.objects.select_related("user")
            .filter(provider=identity.provider, external_id=identity.external_id)
            .first()
        )
        if link is not None:
            return _to_dto(link.user, created=False)

        created = False
        user = None
        if identity.email:
            user = User.objects.filter(email__iexact=identity.email).first()
        if user is None:
            # No password → has_usable_password() is False (Google-only account).
            user = User.objects.create_user(
                username=self._unique_username(identity),
                email=identity.email or "",
                password=None,
            )
            created = True

        ExternalIdentityModel.objects.create(
            user=user,
            provider=identity.provider,
            external_id=identity.external_id,
            email=identity.email or "",
        )
        return _to_dto(user, created=created)

    @staticmethod
    def _unique_username(identity: VerifiedIdentity) -> str:
        base = (
            identity.email.split("@")[0]
            if identity.email
            else f"{identity.provider}_{identity.external_id}"
        )
        base = base[:140] or identity.provider
        candidate, suffix = base, 1
        while User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base}{suffix}"
        return candidate

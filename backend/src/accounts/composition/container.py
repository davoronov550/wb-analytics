"""Accounts composition root."""

from __future__ import annotations

from django.conf import settings

from accounts.adapters.outbound.identity.google import GoogleIdentityVerifier
from accounts.adapters.outbound.persistence.repository import DjangoSavedSearchRepository
from accounts.adapters.outbound.persistence.user_directory import DjangoUserDirectory
from accounts.application.ports import SavedSearchRepositoryPort
from accounts.application.use_cases.authenticate_with_provider import AuthenticateWithProvider
from accounts.application.use_cases.manage_saved_searches import ManageSavedSearches


def build_saved_search_repository() -> SavedSearchRepositoryPort:
    return DjangoSavedSearchRepository()


def build_manage_saved_searches() -> ManageSavedSearches:
    return ManageSavedSearches(repository=build_saved_search_repository())


def build_authenticate_with_google() -> AuthenticateWithProvider:
    return AuthenticateWithProvider(
        verifier=GoogleIdentityVerifier(client_id=settings.GOOGLE_CLIENT_ID),
        directory=DjangoUserDirectory(),
    )

"""Accounts composition root."""

from __future__ import annotations

from accounts.adapters.outbound.persistence.repository import DjangoSavedSearchRepository
from accounts.application.ports import SavedSearchRepositoryPort
from accounts.application.use_cases.manage_saved_searches import ManageSavedSearches


def build_saved_search_repository() -> SavedSearchRepositoryPort:
    return DjangoSavedSearchRepository()


def build_manage_saved_searches() -> ManageSavedSearches:
    return ManageSavedSearches(repository=build_saved_search_repository())

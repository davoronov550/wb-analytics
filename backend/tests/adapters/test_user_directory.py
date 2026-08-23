"""DjangoUserDirectory tests (@django_db, deferred) — find/link/create by identity."""

import pytest
from django.contrib.auth import get_user_model

from accounts.adapters.outbound.persistence.user_directory import DjangoUserDirectory
from accounts.application.dto import VerifiedIdentity

User = get_user_model()


def _identity(email="new@x.io", sub="sub-1"):
    return VerifiedIdentity(provider="google", external_id=sub, email=email, name="New")


@pytest.mark.django_db
def test_provisions_new_password_less_account():
    account = DjangoUserDirectory().find_or_create_by_identity(_identity())

    assert account.created is True
    assert account.email == "new@x.io"
    assert account.providers == ("google",)  # no usable password
    user = User.objects.get(pk=account.id)
    assert user.has_usable_password() is False


@pytest.mark.django_db
def test_is_idempotent_for_same_identity():
    directory = DjangoUserDirectory()
    first = directory.find_or_create_by_identity(_identity())
    second = directory.find_or_create_by_identity(_identity())

    assert first.id == second.id
    assert second.created is False
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_links_identity_to_existing_email_account():
    existing = User.objects.create_user(username="bob", email="bob@x.io", password="pw12345678")

    account = DjangoUserDirectory().find_or_create_by_identity(_identity(email="bob@x.io"))

    assert account.id == existing.id
    assert account.created is False
    # Password login preserved, Google now linked too.
    assert set(account.providers) == {"password", "google"}

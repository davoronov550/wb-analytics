"""Accounts application errors (framework-free)."""

from __future__ import annotations


class InvalidCredential(Exception):
    """Raised when an external credential fails verification."""

"""SQLAlchemy tables owned by this service.

Empty on purpose: the first migration is written against a schema, and there is
no schema yet. What matters is that the wiring exists from the start —
`alembic/env.py` already lists `service_metadata`, so the first table added here
is picked up by autogenerate without anyone remembering to connect it.

The `MetaData` is the service's own, separate from `outbox_metadata`: the outbox
table belongs to the platform and is described there once for all nine services.
Alembic consults both, and refuses a collision between them.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

__all__ = ["Base", "service_metadata"]


class Base(DeclarativeBase):
    metadata = MetaData()


service_metadata = Base.metadata

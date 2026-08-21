"""Django implementation of ParseJobRepositoryPort (outbound adapter)."""

from __future__ import annotations

import uuid

from django.utils import timezone

from catalog.adapters.outbound.persistence.models import ParseJobModel
from catalog.application.dto import ACTIVE_PARSE_STATUSES, ParseJob, ParseStatus


def _to_dto(model: ParseJobModel) -> ParseJob:
    return ParseJob(
        task_id=model.task_id,
        query=model.query,
        status=model.status,
        created=model.created,
        updated=model.updated,
        collected_count=model.created + model.updated,
        error=model.error,
        finished_at=model.finished_at,
    )


class DjangoParseJobRepository:
    def find_active(self, query: str) -> ParseJob | None:
        row = (
            ParseJobModel.objects.filter(query=query, status__in=ACTIVE_PARSE_STATUSES)
            .order_by("-created_at")
            .first()
        )
        return _to_dto(row) if row else None

    def create_pending(self, query: str) -> ParseJob:
        row = ParseJobModel.objects.create(
            task_id=uuid.uuid4().hex,
            query=query,
            status=ParseStatus.PENDING,
        )
        return _to_dto(row)

    def get(self, task_id: str) -> ParseJob | None:
        row = ParseJobModel.objects.filter(pk=task_id).first()
        return _to_dto(row) if row else None

    def mark_running(self, task_id: str) -> None:
        ParseJobModel.objects.filter(pk=task_id).update(status=ParseStatus.RUNNING)

    def mark_done(self, task_id: str, created: int, updated: int) -> None:
        ParseJobModel.objects.filter(pk=task_id).update(
            status=ParseStatus.DONE,
            created=created,
            updated=updated,
            finished_at=timezone.now(),
        )

    def mark_failed(self, task_id: str, error: str) -> None:
        ParseJobModel.objects.filter(pk=task_id).update(
            status=ParseStatus.FAILED,
            error=error,
            finished_at=timezone.now(),
        )

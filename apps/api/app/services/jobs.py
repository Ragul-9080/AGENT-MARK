from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import JobStatus
from app.models.job import Job


def create_job(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    type: str,
    payload: dict[str, Any] | None = None,
) -> Job:
    job = Job(
        workspace_id=workspace_id,
        type=type,
        status=JobStatus.queued,
        progress=0,
        payload=payload or {},
    )
    db.add(job)
    db.flush()
    return job


def get_job_or_404(db: Session, *, workspace_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id))
    if job is None:
        raise AppError(404, "job_not_found", "We could not find that job.")
    return job


def mark_running(db: Session, job: Job, progress: int = 5) -> None:
    job.status = JobStatus.running
    job.progress = max(0, min(progress, 100))
    job.started_at = job.started_at or datetime.now(UTC)
    job.attempts += 1
    db.flush()


def mark_succeeded(db: Session, job: Job, result: dict[str, Any] | None = None) -> None:
    job.status = JobStatus.succeeded
    job.progress = 100
    job.result = result or {}
    job.error = None
    job.finished_at = datetime.now(UTC)
    db.flush()


def mark_failed(db: Session, job: Job, error: str) -> None:
    job.status = JobStatus.failed
    job.error = error[:2000]
    job.finished_at = datetime.now(UTC)
    db.flush()


def mark_dead_letter(db: Session, job: Job, error: str) -> None:
    job.status = JobStatus.dead_letter
    job.error = error[:2000]
    job.finished_at = datetime.now(UTC)
    db.flush()


def list_jobs(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    status: JobStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Job], int]:
    stmt = select(Job).where(Job.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(Job.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)))
    return items, total

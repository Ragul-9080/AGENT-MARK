from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession, OwnerOrAdmin
from app.core.errors import AppError
from app.core.pagination import Pagination, get_pagination
from app.models.enums import JobStatus
from app.models.job import Job
from app.schemas.common import Page
from app.schemas.event import JobOut
from app.services import jobs as job_service
from app.workers.tasks import ping_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

PaginationDep = Annotated[Pagination, Depends(get_pagination)]


@router.get("", response_model=Page[JobOut])
def list_jobs(
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    status: Annotated[JobStatus | None, Query()] = None,
) -> Page[JobOut]:
    items, total = job_service.list_jobs(
        db,
        workspace_id=user.workspace_id,
        status=status,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[JobOut](
        items=[JobOut.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, user: CurrentUser, db: DbSession) -> JobOut:
    job = job_service.get_job_or_404(db, workspace_id=user.workspace_id, job_id=job_id)
    return JobOut.model_validate(job)


@router.post("/ping", response_model=JobOut, status_code=202)
def ping(user: OwnerOrAdmin, db: DbSession) -> JobOut:
    """Enqueue a harmless job to verify the worker pipeline."""

    job = job_service.create_job(db, workspace_id=user.workspace_id, type="system.ping", payload={})
    job_id = job.id
    db.commit()

    try:
        ping_job.delay(str(job_id))
    except Exception as exc:
        logger.exception("could not enqueue ping job %s", job_id)
        failed = db.get(Job, job_id)
        if failed is not None:
            job_service.mark_failed(db, failed, "Queue unavailable")
            db.commit()
        raise AppError(
            503,
            "queue_unavailable",
            "The job queue is not available right now.",
        ) from exc

    db.expire_all()
    fresh = job_service.get_job_or_404(db, workspace_id=user.workspace_id, job_id=job_id)
    return JobOut.model_validate(fresh)

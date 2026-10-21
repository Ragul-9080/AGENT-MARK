from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.models.enums import EventModule, JobStatus
from app.schemas.common import ORMModel


class EventOut(ORMModel):
    id: uuid.UUID
    contact_id: uuid.UUID | None
    source_module: EventModule
    type: str
    payload: dict[str, Any]
    occurred_at: datetime
    created_at: datetime


class JobOut(ORMModel):
    id: uuid.UUID
    type: str
    status: JobStatus
    progress: int
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

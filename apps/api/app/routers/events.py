from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import Pagination, get_pagination
from app.models.enums import EventModule
from app.schemas.common import Page
from app.schemas.event import EventOut
from app.services import events as event_service

router = APIRouter(prefix="/events", tags=["events"])

PaginationDep = Annotated[Pagination, Depends(get_pagination)]


@router.get("", response_model=Page[EventOut])
def list_events(
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    contact_id: Annotated[uuid.UUID | None, Query()] = None,
    module: Annotated[EventModule | None, Query()] = None,
    type: Annotated[str | None, Query(max_length=100)] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> Page[EventOut]:
    items, total = event_service.list_events(
        db,
        workspace_id=user.workspace_id,
        contact_id=contact_id,
        module=module,
        type=type,
        date_from=date_from,
        date_to=date_to,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[EventOut](
        items=[EventOut.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )

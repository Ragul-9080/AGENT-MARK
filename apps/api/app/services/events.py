from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.enums import EventModule
from app.models.event import Event


def record_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    source_module: EventModule,
    type: str,
    contact_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    """The single writer for the cross-module timeline."""

    event = Event(
        workspace_id=workspace_id,
        contact_id=contact_id,
        source_module=source_module,
        type=type,
        payload=payload or {},
        **({"occurred_at": occurred_at} if occurred_at else {}),
    )
    db.add(event)
    return event


def apply_event_filters(
    stmt: Select[tuple[Event]],
    *,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    module: EventModule | None = None,
    type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select[tuple[Event]]:
    stmt = stmt.where(Event.workspace_id == workspace_id)
    if contact_id:
        stmt = stmt.where(Event.contact_id == contact_id)
    if module:
        stmt = stmt.where(Event.source_module == module)
    if type:
        stmt = stmt.where(Event.type == type)
    if date_from:
        stmt = stmt.where(Event.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(Event.occurred_at <= date_to)
    return stmt


def list_events(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    module: EventModule | None = None,
    type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Event], int]:
    base = apply_event_filters(
        select(Event),
        workspace_id=workspace_id,
        contact_id=contact_id,
        module=module,
        type=type,
        date_from=date_from,
        date_to=date_to,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.execute(
            base.order_by(Event.occurred_at.desc(), Event.id.desc()).limit(limit).offset(offset)
        ).scalars()
    )
    return cast(list[Event], items), total

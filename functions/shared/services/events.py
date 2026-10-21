"""Event service for Catalyst functions.

Single writer for the cross-module timeline.
Adapted from apps/api/app/services/events.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shared.models.event import Event
from shared.models.enums import EventModule


def record_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    source_module: str | EventModule,
    type: str,
    contact_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    """Append an event to the workspace timeline."""

    module = source_module.value if hasattr(source_module, "value") else str(source_module)
    event = Event(
        workspace_id=workspace_id,
        contact_id=contact_id,
        source_module=module,
        type=type,
        payload=payload or {},
        **({"occurred_at": occurred_at} if occurred_at else {}),
    )
    db.add(event)
    return event


def list_events(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    module: str | EventModule | None = None,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Event], int]:
    stmt = select(Event).where(Event.workspace_id == workspace_id)
    if contact_id:
        stmt = stmt.where(Event.contact_id == contact_id)
    if module:
        mod = module.value if hasattr(module, "value") else str(module)
        stmt = stmt.where(Event.source_module == mod)
    if type:
        stmt = stmt.where(Event.type == type)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(Event.occurred_at.desc(), Event.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total

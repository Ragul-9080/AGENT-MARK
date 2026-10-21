from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import DbSession, OwnerOrAdmin
from app.core.errors import AppError
from app.core.pagination import validate_calling_window
from app.models.enums import EventModule
from app.models.user import User
from app.schemas.auth import WorkspaceOut
from app.schemas.workspace import MemberOut, WorkspaceUpdate
from app.services.events import record_event

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("", response_model=WorkspaceOut)
def get_workspace(user: OwnerOrAdmin) -> WorkspaceOut:
    return WorkspaceOut.model_validate(user.workspace)


@router.patch("", response_model=WorkspaceOut)
def update_workspace(payload: WorkspaceUpdate, user: OwnerOrAdmin, db: DbSession) -> WorkspaceOut:
    workspace = user.workspace

    if payload.name is not None:
        workspace.name = payload.name.strip()
    if payload.timezone is not None:
        try:
            ZoneInfo(payload.timezone)
        except ZoneInfoNotFoundError as exc:
            raise AppError(422, "invalid_timezone", "Choose a valid time zone.") from exc
        workspace.timezone = payload.timezone
    if payload.default_language is not None:
        workspace.default_language = payload.default_language

    if payload.settings is not None:
        settings_payload: dict[str, Any] = payload.settings
        calling_hours = settings_payload.get("calling_hours")
        if calling_hours is not None:
            if isinstance(calling_hours, str):
                start, end = validate_calling_window(calling_hours)
                settings_payload["calling_hours"] = {
                    "start": start,
                    "end": end,
                    "timezone": "contact",
                }
            elif isinstance(calling_hours, dict):
                raw = f"{calling_hours.get('start', '')}-{calling_hours.get('end', '')}"
                start, end = validate_calling_window(raw)
                settings_payload["calling_hours"] = {
                    "start": start,
                    "end": end,
                    "timezone": calling_hours.get("timezone", "contact"),
                }
            else:
                raise AppError(
                    422,
                    "invalid_calling_window",
                    "Calling hours must be a time range or an object.",
                )
        workspace.settings = settings_payload

    record_event(
        db,
        workspace_id=workspace.id,
        source_module=EventModule.system,
        type="workspace.updated",
        payload={},
    )
    db.flush()
    return WorkspaceOut.model_validate(workspace)


@router.get("/members", response_model=list[MemberOut])
def list_members(user: OwnerOrAdmin, db: DbSession) -> list[MemberOut]:
    members = db.scalars(
        select(User).where(User.workspace_id == user.workspace_id).order_by(User.created_at)
    )
    return [MemberOut.model_validate(member) for member in members]

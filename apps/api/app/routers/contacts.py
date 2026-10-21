from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.errors import AppError
from app.core.pagination import Pagination, get_pagination
from app.models.enums import ConsentChannel, EventModule
from app.schemas.common import Page
from app.schemas.contact import (
    ConsentOut,
    ConsentUpsert,
    ContactCreate,
    ContactOut,
    ContactUpdate,
    EligibilityOut,
    ImportResult,
)
from app.schemas.event import EventOut
from app.services import consent as consent_service
from app.services import contacts as contact_service
from app.services import events as event_service
from app.services import imports as import_service

router = APIRouter(prefix="/contacts", tags=["contacts"])

PaginationDep = Annotated[Pagination, Depends(get_pagination)]


@router.get("", response_model=Page[ContactOut])
def list_contacts(
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    tag: Annotated[str | None, Query(max_length=50)] = None,
    language: Annotated[str | None, Query(max_length=16)] = None,
    source: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[ContactOut]:
    items, total = contact_service.list_contacts(
        db,
        workspace_id=user.workspace_id,
        search=search,
        tag=tag,
        language=language,
        source=source,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[ContactOut](
        items=[ContactOut.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=ContactOut, status_code=201)
def create_contact(payload: ContactCreate, user: CurrentUser, db: DbSession) -> ContactOut:
    contact = contact_service.create_contact(db, workspace_id=user.workspace_id, data=payload)
    return ContactOut.model_validate(contact)


@router.post("/import", response_model=ImportResult)
async def import_contacts(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Query()] = True,
) -> ImportResult:
    content = await file.read(settings.contact_import_max_bytes + 1)
    if not content:
        raise AppError(422, "empty_file", "The CSV file is empty.")
    if len(content) > settings.contact_import_max_bytes:
        raise AppError(
            422,
            "import_too_large",
            "The file is larger than 5 MB. Split it and try again.",
        )

    workspace = user.workspace
    return import_service.import_contacts(db, workspace=workspace, content=content, dry_run=dry_run)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ContactOut:
    contact = contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    return ContactOut.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    payload: ContactUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ContactOut:
    contact = contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    contact = contact_service.update_contact(
        db, workspace_id=user.workspace_id, contact=contact, data=payload
    )
    return ContactOut.model_validate(contact)


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    contact = contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    contact_service.delete_contact(db, workspace_id=user.workspace_id, contact=contact)
    return Response(status_code=204)


@router.get("/{contact_id}/events", response_model=Page[EventOut])
def contact_events(
    contact_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    module: Annotated[EventModule | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
) -> Page[EventOut]:
    contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    items, total = event_service.list_events(
        db,
        workspace_id=user.workspace_id,
        contact_id=contact_id,
        module=module,
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


@router.get("/{contact_id}/consents", response_model=list[ConsentOut])
def list_consents(contact_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[ConsentOut]:
    contact = contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    return [
        ConsentOut.model_validate(consent)
        for consent in consent_service.list_consents(db, contact=contact)
    ]


@router.put("/{contact_id}/consents/{channel}", response_model=ConsentOut)
def upsert_consent(
    contact_id: uuid.UUID,
    channel: ConsentChannel,
    payload: ConsentUpsert,
    user: CurrentUser,
    db: DbSession,
) -> ConsentOut:
    contact = contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    consent = consent_service.upsert_consent(db, contact=contact, channel=channel, data=payload)
    return ConsentOut.model_validate(consent)


@router.get("/{contact_id}/eligibility", response_model=EligibilityOut)
def contact_eligibility(contact_id: uuid.UUID, user: CurrentUser, db: DbSession) -> EligibilityOut:
    contact = contact_service.get_contact_or_404(db, user.workspace_id, contact_id)
    return consent_service.eligibility(db, contact=contact)

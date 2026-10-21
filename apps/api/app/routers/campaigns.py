from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.deps import CurrentUser, DbSession
from app.core.pagination import Pagination, get_pagination
from app.models.enums import CampaignStatus, CampaignType
from app.schemas.campaign import (
    CampaignAddContacts,
    CampaignAddContactsResult,
    CampaignContactOut,
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
)
from app.schemas.common import Page
from app.services import campaigns as campaign_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

PaginationDep = Annotated[Pagination, Depends(get_pagination)]


@router.get("", response_model=Page[CampaignOut])
def list_campaigns(
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
    type: Annotated[CampaignType | None, Query()] = None,
    status: Annotated[CampaignStatus | None, Query()] = None,
) -> Page[CampaignOut]:
    items, total = campaign_service.list_campaigns(
        db,
        workspace_id=user.workspace_id,
        type=type,
        status=status,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[CampaignOut](
        items=[CampaignOut.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, user: CurrentUser, db: DbSession) -> CampaignOut:
    campaign = campaign_service.create_campaign(db, workspace_id=user.workspace_id, data=payload)
    return CampaignOut.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CampaignOut:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    return CampaignOut.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    user: CurrentUser,
    db: DbSession,
) -> CampaignOut:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    campaign = campaign_service.update_campaign(db, campaign=campaign, data=payload)
    return CampaignOut.model_validate(campaign)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    campaign_service.delete_campaign(db, campaign=campaign)
    return Response(status_code=204)


@router.post("/{campaign_id}/start", response_model=CampaignOut)
def start_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CampaignOut:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    campaign = campaign_service.start_campaign(db, campaign=campaign, actor_id=user.id)
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
def pause_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CampaignOut:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    campaign = campaign_service.pause_campaign(db, campaign=campaign, actor_id=user.id)
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/resume", response_model=CampaignOut)
def resume_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CampaignOut:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    campaign = campaign_service.resume_campaign(db, campaign=campaign, actor_id=user.id)
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/stop", response_model=CampaignOut)
def stop_campaign(campaign_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CampaignOut:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    campaign = campaign_service.stop_campaign(db, campaign=campaign, actor_id=user.id)
    return CampaignOut.model_validate(campaign)


@router.post("/{campaign_id}/contacts", response_model=CampaignAddContactsResult)
def add_campaign_contacts(
    campaign_id: uuid.UUID,
    payload: CampaignAddContacts,
    user: CurrentUser,
    db: DbSession,
) -> CampaignAddContactsResult:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    added, skipped, missing = campaign_service.add_contacts(
        db, campaign=campaign, contact_ids=payload.contact_ids
    )
    return CampaignAddContactsResult(added=added, skipped=skipped, missing=missing)


@router.get("/{campaign_id}/contacts", response_model=Page[CampaignContactOut])
def list_campaign_contacts(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    pagination: PaginationDep,
) -> Page[CampaignContactOut]:
    campaign = campaign_service.get_campaign_or_404(
        db, workspace_id=user.workspace_id, campaign_id=campaign_id
    )
    items, total = campaign_service.list_campaign_contacts(
        db, campaign=campaign, limit=pagination.limit, offset=pagination.offset
    )
    return Page[CampaignContactOut](
        items=[CampaignContactOut.model_validate(item) for item in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )

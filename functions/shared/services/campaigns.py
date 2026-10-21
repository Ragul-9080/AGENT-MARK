"""Campaign service for Catalyst functions.

Campaign state machine, recipients, scheduler promotion.
Adapted from apps/api/app/services/campaigns.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from shared.core.errors import AppError
from shared.models.campaign import Campaign, CampaignContact
from shared.models.contact import Contact
from shared.models.enums import (
    CampaignContactStatus,
    CampaignStatus,
    EventModule,
)
from shared.services.events import record_event

TERMINAL_STATUSES = {CampaignStatus.completed, CampaignStatus.failed}


def get_campaign_or_404(
    db: Session, *, workspace_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    )
    if campaign is None:
        raise AppError(404, "campaign_not_found", "We could not find that campaign.")
    return campaign


def create_campaign(
    db: Session, *, workspace_id: uuid.UUID, data: dict[str, Any]
) -> Campaign:
    from shared.models.enums import CampaignType

    campaign = Campaign(
        workspace_id=workspace_id,
        type=CampaignType(data["type"]),
        name=data["name"].strip(),
        status=CampaignStatus.draft,
        scheduled_at=data.get("scheduled_at"),
        settings=data.get("settings") or {},
    )
    db.add(campaign)
    db.flush()
    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.system,
        type="campaign.created",
        payload={"campaign_id": str(campaign.id), "campaign_type": campaign.type.value},
    )
    return campaign


def list_campaigns(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Campaign], int]:
    stmt = select(Campaign).where(Campaign.workspace_id == workspace_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(Campaign.created_at.desc(), Campaign.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def start_campaign(
    db: Session, *, campaign: Campaign, actor_id: uuid.UUID
) -> Campaign:
    if campaign.status not in {CampaignStatus.draft, CampaignStatus.scheduled}:
        raise AppError(
            409,
            "invalid_campaign_transition",
            f"You cannot start a campaign that is {campaign.status.value}.",
        )
    now = datetime.now(UTC)
    if campaign.scheduled_at is not None and campaign.scheduled_at > now:
        campaign.status = CampaignStatus.scheduled
    else:
        campaign.status = CampaignStatus.running
    record_event(
        db,
        workspace_id=campaign.workspace_id,
        source_module=EventModule.system,
        type="campaign.started",
        payload={"campaign_id": str(campaign.id), "actor_id": str(actor_id)},
    )
    db.flush()
    return campaign


def pause_campaign(
    db: Session, *, campaign: Campaign, actor_id: uuid.UUID
) -> Campaign:
    if campaign.status != CampaignStatus.running:
        raise AppError(
            409,
            "invalid_campaign_transition",
            f"You cannot pause a campaign that is {campaign.status.value}.",
        )
    campaign.status = CampaignStatus.paused
    record_event(
        db,
        workspace_id=campaign.workspace_id,
        source_module=EventModule.system,
        type="campaign.paused",
        payload={"campaign_id": str(campaign.id), "actor_id": str(actor_id)},
    )
    db.flush()
    return campaign


def resume_campaign(
    db: Session, *, campaign: Campaign, actor_id: uuid.UUID
) -> Campaign:
    if campaign.status != CampaignStatus.paused:
        raise AppError(
            409,
            "invalid_campaign_transition",
            f"You cannot resume a campaign that is {campaign.status.value}.",
        )
    campaign.status = CampaignStatus.running
    record_event(
        db,
        workspace_id=campaign.workspace_id,
        source_module=EventModule.system,
        type="campaign.resumed",
        payload={"campaign_id": str(campaign.id), "actor_id": str(actor_id)},
    )
    db.flush()
    return campaign


def stop_campaign(
    db: Session, *, campaign: Campaign, actor_id: uuid.UUID
) -> Campaign:
    if campaign.status not in {
        CampaignStatus.draft,
        CampaignStatus.scheduled,
        CampaignStatus.running,
        CampaignStatus.paused,
    }:
        raise AppError(
            409,
            "invalid_campaign_transition",
            f"You cannot stop a campaign that is {campaign.status.value}.",
        )
    campaign.status = CampaignStatus.completed
    record_event(
        db,
        workspace_id=campaign.workspace_id,
        source_module=EventModule.system,
        type="campaign.stopped",
        payload={"campaign_id": str(campaign.id), "actor_id": str(actor_id)},
    )
    db.flush()
    return campaign

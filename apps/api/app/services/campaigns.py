from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.models.campaign import Campaign, CampaignContact
from app.models.contact import Contact
from app.models.enums import CampaignContactStatus, CampaignStatus, EventModule
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.services.events import record_event

TERMINAL_STATUSES = {CampaignStatus.completed, CampaignStatus.failed}


def _campaign_event(
    db: Session,
    campaign: Campaign,
    type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    record_event(
        db,
        workspace_id=campaign.workspace_id,
        source_module=EventModule.system,
        type=type,
        payload={
            "campaign_id": str(campaign.id),
            "campaign_type": campaign.type.value,
            "status": campaign.status.value,
            **(payload or {}),
        },
    )


def get_campaign_or_404(
    db: Session, *, workspace_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    )
    if campaign is None:
        raise AppError(404, "campaign_not_found", "We could not find that campaign.")
    return campaign


def create_campaign(db: Session, *, workspace_id: uuid.UUID, data: CampaignCreate) -> Campaign:
    campaign = Campaign(
        workspace_id=workspace_id,
        type=data.type,
        name=data.name.strip(),
        status=CampaignStatus.draft,
        scheduled_at=data.scheduled_at,
        settings=data.settings,
    )
    db.add(campaign)
    db.flush()
    _campaign_event(db, campaign, "campaign.created")
    return campaign


def update_campaign(db: Session, *, campaign: Campaign, data: CampaignUpdate) -> Campaign:
    if campaign.status in {CampaignStatus.running}:
        raise AppError(
            409,
            "campaign_running",
            "Pause the campaign before changing it.",
        )

    updates = data.model_dump(exclude_unset=True)
    if "name" in updates:
        campaign.name = (updates["name"] or "").strip()
    if "scheduled_at" in updates:
        campaign.scheduled_at = updates["scheduled_at"]
    if "settings" in updates:
        campaign.settings = updates["settings"] or {}
    db.flush()
    _campaign_event(db, campaign, "campaign.updated")
    return campaign


def list_campaigns(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    type: Any | None = None,
    status: CampaignStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Campaign], int]:
    stmt = select(Campaign).where(Campaign.workspace_id == workspace_id)
    if type is not None:
        stmt = stmt.where(Campaign.type == type)
    if status is not None:
        stmt = stmt.where(Campaign.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.order_by(Campaign.created_at.desc(), Campaign.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def _conflict(campaign: Campaign, action: str) -> AppError:
    return AppError(
        409,
        "invalid_campaign_transition",
        f"You cannot {action} a campaign that is {campaign.status.value.replace('_', ' ')}.",
    )


def start_campaign(db: Session, *, campaign: Campaign, actor_id: uuid.UUID) -> Campaign:
    if campaign.status not in {CampaignStatus.draft, CampaignStatus.scheduled}:
        raise _conflict(campaign, "start")

    now = datetime.now(UTC)
    if campaign.scheduled_at is not None and campaign.scheduled_at > now:
        campaign.status = CampaignStatus.scheduled
        _campaign_event(
            db,
            campaign,
            "campaign.scheduled",
            {"scheduled_at": campaign.scheduled_at.isoformat(), "actor_id": str(actor_id)},
        )
    else:
        campaign.status = CampaignStatus.running
        _campaign_event(db, campaign, "campaign.started", {"actor_id": str(actor_id)})

    db.flush()
    return campaign


def pause_campaign(db: Session, *, campaign: Campaign, actor_id: uuid.UUID) -> Campaign:
    if campaign.status != CampaignStatus.running:
        raise _conflict(campaign, "pause")
    campaign.status = CampaignStatus.paused
    _campaign_event(db, campaign, "campaign.paused", {"actor_id": str(actor_id)})
    db.flush()
    return campaign


def resume_campaign(db: Session, *, campaign: Campaign, actor_id: uuid.UUID) -> Campaign:
    if campaign.status != CampaignStatus.paused:
        raise _conflict(campaign, "resume")
    campaign.status = CampaignStatus.running
    _campaign_event(db, campaign, "campaign.resumed", {"actor_id": str(actor_id)})
    db.flush()
    return campaign


def stop_campaign(db: Session, *, campaign: Campaign, actor_id: uuid.UUID) -> Campaign:
    if campaign.status not in {
        CampaignStatus.draft,
        CampaignStatus.scheduled,
        CampaignStatus.running,
        CampaignStatus.paused,
    }:
        raise _conflict(campaign, "stop")
    campaign.status = CampaignStatus.completed
    _campaign_event(db, campaign, "campaign.stopped", {"actor_id": str(actor_id)})
    db.flush()
    return campaign


def fail_campaign(db: Session, *, campaign: Campaign, reason: str) -> Campaign:
    campaign.status = CampaignStatus.failed
    _campaign_event(db, campaign, "campaign.failed", {"reason": reason})
    db.flush()
    return campaign


def delete_campaign(db: Session, *, campaign: Campaign) -> None:
    if campaign.status in {CampaignStatus.running, CampaignStatus.paused}:
        raise AppError(
            409,
            "campaign_running",
            "Stop the campaign before deleting it.",
        )
    _campaign_event(db, campaign, "campaign.deleted")
    db.delete(campaign)
    db.flush()


def add_contacts(
    db: Session,
    *,
    campaign: Campaign,
    contact_ids: list[uuid.UUID],
) -> tuple[int, int, int]:
    if campaign.status in {
        CampaignStatus.running,
        CampaignStatus.completed,
        CampaignStatus.failed,
    }:
        raise AppError(
            409,
            "campaign_not_editable",
            "Recipients can only be changed while a campaign is a draft or paused.",
        )

    unique_ids = list(dict.fromkeys(contact_ids))
    contacts = list(
        db.scalars(
            select(Contact).where(
                Contact.workspace_id == campaign.workspace_id, Contact.id.in_(unique_ids)
            )
        )
    )
    found_ids = {contact.id for contact in contacts}
    missing = len(unique_ids) - len(found_ids)

    existing_ids = (
        set(
            db.scalars(
                select(CampaignContact.contact_id).where(
                    CampaignContact.campaign_id == campaign.id,
                    CampaignContact.contact_id.in_(found_ids),
                )
            )
        )
        if found_ids
        else set()
    )

    added = 0
    for contact in contacts:
        if contact.id in existing_ids:
            continue
        db.add(
            CampaignContact(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                contact_id=contact.id,
                status=CampaignContactStatus.pending,
            )
        )
        added += 1

    skipped = len(found_ids) - added
    db.flush()
    _campaign_event(
        db,
        campaign,
        "campaign.recipients_added",
        {"added": added, "skipped": skipped, "missing": missing},
    )
    return added, skipped, missing


def list_campaign_contacts(
    db: Session,
    *,
    campaign: Campaign,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CampaignContact], int]:
    stmt = (
        select(CampaignContact)
        .where(
            CampaignContact.campaign_id == campaign.id,
            CampaignContact.workspace_id == campaign.workspace_id,
        )
        .options(selectinload(CampaignContact.contact))
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(stmt.order_by(CampaignContact.created_at.asc()).limit(limit).offset(offset))
    )
    return items, total


def promote_due_campaigns(db: Session) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    due = list(
        db.scalars(
            select(Campaign).where(
                Campaign.status == CampaignStatus.scheduled,
                Campaign.scheduled_at.is_not(None),
                Campaign.scheduled_at <= now,
            )
        )
    )
    for campaign in due:
        campaign.status = CampaignStatus.running
        _campaign_event(db, campaign, "campaign.started", {"trigger": "scheduler"})
    db.flush()
    return [campaign.id for campaign in due]

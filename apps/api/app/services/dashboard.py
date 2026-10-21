from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.contact import Contact
from app.models.email import EmailMessage
from app.models.enums import CampaignStatus, SeoAuditStatus
from app.models.event import Event
from app.models.seo import SeoAudit
from app.models.voice import Call
from app.schemas.dashboard import DashboardSummary


def summary(db: Session, *, workspace_id: uuid.UUID) -> DashboardSummary:
    contacts = (
        db.scalar(
            select(func.count()).select_from(Contact).where(Contact.workspace_id == workspace_id)
        )
        or 0
    )
    calls = (
        db.scalar(select(func.count()).select_from(Call).where(Call.workspace_id == workspace_id))
        or 0
    )
    emails_sent = (
        db.scalar(
            select(func.count())
            .select_from(EmailMessage)
            .where(
                EmailMessage.workspace_id == workspace_id,
                EmailMessage.sent_at.is_not(None),
            )
        )
        or 0
    )
    latest_seo_score = db.scalar(
        select(SeoAudit.health_score)
        .where(
            SeoAudit.workspace_id == workspace_id,
            SeoAudit.status == SeoAuditStatus.completed,
            SeoAudit.health_score.is_not(None),
        )
        .order_by(SeoAudit.completed_at.desc().nulls_last(), SeoAudit.created_at.desc())
        .limit(1)
    )
    running_campaigns = (
        db.scalar(
            select(func.count())
            .select_from(Campaign)
            .where(
                Campaign.workspace_id == workspace_id,
                Campaign.status == CampaignStatus.running,
            )
        )
        or 0
    )
    active_campaigns = list(
        db.scalars(
            select(Campaign)
            .where(
                Campaign.workspace_id == workspace_id,
                Campaign.status.in_(
                    [CampaignStatus.running, CampaignStatus.scheduled, CampaignStatus.paused]
                ),
            )
            .order_by(Campaign.updated_at.desc())
            .limit(5)
        )
    )
    recent_events = list(
        db.scalars(
            select(Event)
            .where(Event.workspace_id == workspace_id)
            .order_by(Event.occurred_at.desc(), Event.id.desc())
            .limit(10)
        )
    )

    return DashboardSummary(
        contacts=contacts,
        calls=calls,
        emails_sent=emails_sent,
        latest_seo_score=latest_seo_score,
        running_campaigns=running_campaigns,
        active_campaigns=active_campaigns,
        recent_events=recent_events,
    )

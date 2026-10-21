"""Email service for Catalyst functions.

Send, list, webhook processing. Consent + suppression gated.
Adapted from apps/api/app/services/email.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from shared.core.errors import AppError
from shared.integrations.email import get_email_provider
from shared.models.campaign import Campaign
from shared.models.contact import Contact
from shared.models.email import EmailMessage, EmailEvent
from shared.models.enums import (
    CampaignStatus,
    ConsentChannel,
    EmailEventType,
    EmailMessageStatus,
    EventModule,
    SuppressionReason,
)
from shared.schemas.email import EmailSend, EmailWebhookEvent
from shared.services import consent as consent_service
from shared.services.events import record_event
from shared.services.jobs import create_job


def get_email_message_or_404(
    db: Session, *, workspace_id: uuid.UUID, message_id: uuid.UUID
) -> EmailMessage:
    message = db.scalar(
        select(EmailMessage).where(
            EmailMessage.id == message_id, EmailMessage.workspace_id == workspace_id
        )
    )
    if message is None:
        raise AppError(404, "email_message_not_found", "We could not find that email.")
    return message


def send_email(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    data: EmailSend,
    actor_id: uuid.UUID | None = None,
) -> EmailMessage:
    """Send a single email to a contact.

    Enforces consent + suppression, creates an EmailMessage in queued state,
    and queues a job for delivery. Returns the message.
    """

    contact: Contact | None = None
    if data.contact_id is not None:
        contact = db.scalar(
            select(Contact).where(
                Contact.id == data.contact_id,
                Contact.workspace_id == workspace_id,
            )
        )
        if contact is None:
            raise AppError(404, "contact_not_found", "We could not find that contact.")
    elif data.to:
        contact = db.scalar(
            select(Contact).where(
                Contact.workspace_id == workspace_id,
                func.lower(Contact.email) == func.lower(str(data.to)),
            )
        )
        if contact is None:
            raise AppError(
                404,
                "contact_not_found",
                "No contact with that email address in this workspace.",
            )

    if contact is None:
        raise AppError(422, "contact_required", "Provide a contact_id or a known recipient.")

    eligibility = consent_service.check_channel_allowed(
        db,
        workspace_id=workspace_id,
        contact=contact,
        channel=ConsentChannel.email,
    )
    if not eligibility.allowed:
        raise AppError(
            409,
            "email_not_allowed",
            eligibility.message or "This contact cannot receive email.",
            details=[{"reason": eligibility.reason}] if eligibility.reason else None,
        )

    campaign: Campaign | None = None
    if data.campaign_id is not None:
        campaign = db.scalar(
            select(Campaign).where(
                Campaign.id == data.campaign_id,
                Campaign.workspace_id == workspace_id,
            )
        )
        if campaign is None:
            raise AppError(404, "campaign_not_found", "We could not find that campaign.")
        if campaign.status not in {
            CampaignStatus.draft,
            CampaignStatus.running,
        }:
            raise AppError(
                409,
                "campaign_not_editable",
                "Email can only be queued for draft or running campaigns.",
            )

    message = EmailMessage(
        workspace_id=workspace_id,
        campaign_id=data.campaign_id,
        contact_id=contact.id,
        subject=data.subject,
        body_html=data.body_html or "",
        body_text=data.body_text,
        status=EmailMessageStatus.queued,
    )
    db.add(message)
    db.flush()

    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.email,
        type="email.queued",
        contact_id=contact.id,
        payload={
            "message_id": str(message.id),
            "campaign_id": str(message.campaign_id) if message.campaign_id else None,
            "recipient_domain": str(data.to).split("@")[-1],
        },
    )

    create_job(
        db,
        workspace_id=workspace_id,
        type="email.send",
        payload={"message_id": str(message.id), "actor_id": str(actor_id) if actor_id else None},
    )

    return message


def list_email_messages(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    status: EmailMessageStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EmailMessage], int]:
    stmt = select(EmailMessage).where(EmailMessage.workspace_id == workspace_id)
    if campaign_id is not None:
        stmt = stmt.where(EmailMessage.campaign_id == campaign_id)
    if contact_id is not None:
        stmt = stmt.where(EmailMessage.contact_id == contact_id)
    if status is not None:
        stmt = stmt.where(EmailMessage.status == status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(
            stmt.options(selectinload(EmailMessage.events))
            .order_by(EmailMessage.created_at.desc(), EmailMessage.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def record_webhook_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    event: EmailWebhookEvent,
) -> EmailMessage | None:
    """Process an inbound provider webhook (SES bounce/complaint/delivery/etc)."""

    message: EmailMessage | None = None
    if event.message_id:
        message = db.scalar(
            select(EmailMessage).where(
                EmailMessage.provider_message_id == event.message_id,
                EmailMessage.workspace_id == workspace_id,
            )
        )

    if message is None:
        return None

    new_status = _webhook_status(event.event_type)
    if new_status is not None and message.status != new_status:
        message.status = new_status
        if new_status == EmailMessageStatus.sent:
            message.sent_at = datetime.now(UTC)
        db.flush()

    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.email,
        contact_id=message.contact_id,
        type=f"email.webhook.{event.event_type}",
        payload={
            "message_id": str(message.id),
            "provider_message_id": event.message_id,
            "meta": event.meta,
        },
    )

    db.add(
        EmailEvent(
            workspace_id=workspace_id,
            message_id=message.id,
            type=_event_type(event.event_type),
            meta=event.meta,
        )
    )
    db.flush()

    if event.event_type.lower() in {"bounce", "complaint"} and message.contact_id is not None:
        contact = db.get(Contact, message.contact_id)
        if contact is not None and contact.email:
            _suppress_address(
                db,
                workspace_id=workspace_id,
                value=contact.email,
                reason=SuppressionReason.bounce,
            )

    return message


def _webhook_status(event_type: str) -> EmailMessageStatus | None:
    mapping = {
        "send": EmailMessageStatus.sent,
        "delivery": EmailMessageStatus.delivered,
        "bounce": EmailMessageStatus.bounced,
        "complaint": EmailMessageStatus.complained,
        "failed": EmailMessageStatus.failed,
    }
    return mapping.get(event_type.lower())


def _event_type(event_type: str) -> EmailEventType:
    normalized = event_type.lower()
    if normalized == "delivery":
        normalized = "delivered"
    try:
        return EmailEventType(normalized)
    except ValueError:
        return EmailEventType.bounce


def _suppress_address(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    value: str,
    reason: SuppressionReason,
) -> None:
    normalized = normalize_email(value)
    if normalized is None:
        return
    existing = db.scalar(
        select(Suppression).where(
            Suppression.workspace_id == workspace_id,
            Suppression.channel == ConsentChannel.email,
            Suppression.value == normalized,
        )
    )
    if existing is not None:
        return

    from shared.models.consent import Suppression

    db.add(
        Suppression(
            workspace_id=workspace_id,
            channel=ConsentChannel.email,
            value=normalized,
            reason=reason,
        )
    )
    db.flush()
    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.email,
        type="suppression.created_from_webhook",
        payload={"channel": "email", "reason": reason.value},
    )

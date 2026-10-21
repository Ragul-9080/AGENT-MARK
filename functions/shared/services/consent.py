"""Consent service for Catalyst functions.

Consent gate, suppression list, eligibility checking.
Adapted from apps/api/app/services/consent.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session

from shared.core.errors import AppError
from shared.models.consent import Consent, Suppression
from shared.models.contact import Contact
from shared.models.enums import (
    ConsentChannel,
    ConsentStatus,
    EventModule,
    SuppressionReason,
)
from shared.schemas.contact import (
    ChannelEligibility,
    ConsentUpsert,
    EligibilityOut,
    SuppressionCreate,
)
from shared.services.contacts import normalize_email
from shared.services.events import record_event


def get_consent(
    db: Session, *, contact_id: uuid.UUID, channel: ConsentChannel
) -> Consent | None:
    return db.scalar(
        select(Consent).where(Consent.contact_id == contact_id, Consent.channel == channel)
    )


def upsert_consent(
    db: Session, *, contact: Contact, channel: ConsentChannel, data: ConsentUpsert
) -> Consent:
    consent = get_consent(db, contact_id=contact.id, channel=channel)
    if consent is None:
        consent = Consent(
            workspace_id=contact.workspace_id,
            contact_id=contact.id,
            channel=channel,
            status=data.status,
            proof=data.proof,
            recorded_at=data.recorded_at or datetime.now(UTC),
        )
        db.add(consent)
    else:
        consent.status = data.status
        consent.proof = data.proof
        consent.recorded_at = data.recorded_at or datetime.now(UTC)

    db.flush()
    record_event(
        db,
        workspace_id=contact.workspace_id,
        source_module=EventModule.system,
        type=f"consent.{data.status.value}",
        contact_id=contact.id,
        payload={"channel": channel.value, "has_proof": bool(data.proof)},
    )
    return consent


def check_channel_allowed(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    contact: Contact,
    channel: ConsentChannel,
) -> ChannelEligibility:
    value = contact.phone if channel == ConsentChannel.voice else contact.email
    if not value:
        label = "phone number" if channel == ConsentChannel.voice else "email address"
        return ChannelEligibility(
            allowed=False,
            reason="missing_contact_details",
            message=f"This contact has no {label}.",
        )

    suppression = db.scalar(
        select(Suppression).where(
            Suppression.workspace_id == workspace_id,
            Suppression.channel == channel,
            Suppression.value == value,
        )
    )
    if suppression is not None:
        return ChannelEligibility(
            allowed=False,
            reason=f"suppressed_{suppression.reason.value}",
            message=f"This contact is on the suppression list ({suppression.reason.value}).",
        )

    consent = get_consent(db, contact_id=contact.id, channel=channel)
    if consent is None or consent.status != ConsentStatus.granted:
        channel_label = "calls" if channel == ConsentChannel.voice else "email"
        return ChannelEligibility(
            allowed=False,
            reason="no_consent",
            message=f"No recorded consent for {channel_label}.",
        )

    return ChannelEligibility(allowed=True, reason=None, message="Ready to contact.")


def create_suppression(
    db: Session, *, workspace_id: uuid.UUID, data: SuppressionCreate
) -> Suppression:
    value = normalize_email(data.value)
    if value is None and data.channel == ConsentChannel.email:
        raise AppError(422, "invalid_email", "Enter a valid email address.")

    existing = db.scalar(
        select(Suppression).where(
            Suppression.workspace_id == workspace_id,
            Suppression.channel == data.channel,
            Suppression.value == value,
        )
    )
    if existing is not None:
        raise AppError(
            409,
            "duplicate_suppression",
            "That phone number or email is already on the suppression list.",
        )

    suppression = Suppression(
        workspace_id=workspace_id,
        channel=data.channel,
        value=value,
        reason=data.reason,
    )
    db.add(suppression)
    db.flush()
    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.system,
        type="suppression.created",
        payload={"channel": data.channel.value, "reason": data.reason.value},
    )
    return suppression

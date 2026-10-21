from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.consent import Consent, Suppression
from app.models.contact import Contact
from app.models.enums import (
    ConsentChannel,
    ConsentStatus,
    EventModule,
)
from app.schemas.contact import (
    ChannelEligibility,
    ConsentUpsert,
    EligibilityOut,
    SuppressionCreate,
)
from app.services.contacts import normalize_email, normalize_phone
from app.services.events import record_event


def get_consent(db: Session, *, contact_id: uuid.UUID, channel: ConsentChannel) -> Consent | None:
    return db.scalar(
        select(Consent).where(Consent.contact_id == contact_id, Consent.channel == channel)
    )


def list_consents(db: Session, *, contact: Contact) -> list[Consent]:
    return list(
        db.scalars(
            select(Consent)
            .where(Consent.contact_id == contact.id, Consent.workspace_id == contact.workspace_id)
            .order_by(Consent.channel)
        )
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


def _normalize_channel_value(channel: ConsentChannel, value: str) -> str:
    if channel == ConsentChannel.voice:
        normalized = normalize_phone(value)
        if normalized is None:
            raise AppError(422, "invalid_phone", "Enter a valid phone number.")
        return normalized
    normalized = normalize_email(value)
    if normalized is None:
        raise AppError(422, "invalid_email", "Enter a valid email address.")
    return normalized


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


def eligibility(db: Session, *, contact: Contact) -> EligibilityOut:
    return EligibilityOut(
        contact_id=contact.id,
        voice=check_channel_allowed(
            db,
            workspace_id=contact.workspace_id,
            contact=contact,
            channel=ConsentChannel.voice,
        ),
        email=check_channel_allowed(
            db,
            workspace_id=contact.workspace_id,
            contact=contact,
            channel=ConsentChannel.email,
        ),
    )


def create_suppression(
    db: Session, *, workspace_id: uuid.UUID, data: SuppressionCreate
) -> Suppression:
    value = _normalize_channel_value(data.channel, data.value)

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
            details=[{"existing_suppression_id": str(existing.id)}],
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


def delete_suppression(db: Session, *, workspace_id: uuid.UUID, suppression: Suppression) -> None:
    record_event(
        db,
        workspace_id=workspace_id,
        source_module=EventModule.system,
        type="suppression.removed",
        payload={"channel": suppression.channel.value, "reason": suppression.reason.value},
    )
    db.delete(suppression)
    db.flush()


def get_suppression_or_404(
    db: Session, *, workspace_id: uuid.UUID, suppression_id: uuid.UUID
) -> Suppression:
    suppression = db.scalar(
        select(Suppression).where(
            Suppression.id == suppression_id, Suppression.workspace_id == workspace_id
        )
    )
    if suppression is None:
        raise AppError(404, "suppression_not_found", "We could not find that suppression.")
    return suppression


def list_suppressions(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    channel: ConsentChannel | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Suppression], int]:
    stmt = select(Suppression).where(Suppression.workspace_id == workspace_id)
    if channel:
        stmt = stmt.where(Suppression.channel == channel)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Suppression.value.ilike(term),
                cast(Suppression.reason, String).ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(
        db.scalars(stmt.order_by(Suppression.created_at.desc()).limit(limit).offset(offset))
    )
    return items, total

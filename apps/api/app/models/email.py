from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.models.enums import (
    EmailEventType,
    EmailMessageStatus,
    enum_column_type,
)

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.contact import Contact


class EmailMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "email_messages"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[EmailMessageStatus] = mapped_column(
        enum_column_type(EmailMessageStatus, "email_message_status", 20),
        nullable=False,
        default=EmailMessageStatus.queued,
        server_default=EmailMessageStatus.queued.value,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped[Campaign | None] = relationship()
    contact: Mapped[Contact | None] = relationship(back_populates="email_messages")
    events: Mapped[list[EmailEvent]] = relationship(
        back_populates="message", cascade="all, delete-orphan", passive_deletes=True
    )


class EmailEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "email_events"

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[EmailEventType] = mapped_column(
        enum_column_type(EmailEventType, "email_event_type", 20), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    message: Mapped[EmailMessage] = relationship(back_populates="events")

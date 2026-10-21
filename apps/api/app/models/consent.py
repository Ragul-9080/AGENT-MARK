from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.models.enums import (
    ConsentChannel,
    ConsentStatus,
    SuppressionReason,
    enum_column_type,
)

if TYPE_CHECKING:
    from app.models.contact import Contact


class Consent(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint("contact_id", "channel", name="uq_consents_contact_channel"),
    )

    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[ConsentChannel] = mapped_column(
        enum_column_type(ConsentChannel, "consent_channel", 16), nullable=False
    )
    status: Mapped[ConsentStatus] = mapped_column(
        enum_column_type(ConsentStatus, "consent_status", 16), nullable=False
    )
    proof: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    contact: Mapped[Contact] = relationship(back_populates="consents")


class Suppression(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "suppressions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "channel", "value", name="uq_suppressions_workspace_channel_value"
        ),
    )

    channel: Mapped[ConsentChannel] = mapped_column(
        enum_column_type(ConsentChannel, "suppression_channel", 16), nullable=False
    )
    value: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    reason: Mapped[SuppressionReason] = mapped_column(
        enum_column_type(SuppressionReason, "suppression_reason", 24),
        nullable=False,
        default=SuppressionReason.manual,
        server_default=text("'manual'"),
    )

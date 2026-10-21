"""Consent and Suppression models for Catalyst functions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceScopedMixin
from shared.models.enums import ConsentChannel, ConsentStatus, SuppressionReason, enum_column_type


class Consent(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "consents"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[ConsentChannel] = mapped_column(
        enum_column_type(ConsentChannel, "consent_channel", 16), nullable=False
    )
    status: Mapped[ConsentStatus] = mapped_column(
        enum_column_type(ConsentStatus, "consent_status", 16), nullable=False
    )
    proof: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False)

    contact: Mapped["Contact"] = relationship(back_populates="consents")


class Suppression(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "suppressions"

    channel: Mapped[ConsentChannel] = mapped_column(
        enum_column_type(ConsentChannel, "suppression_channel", 16), nullable=False
    )
    value: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[SuppressionReason] = mapped_column(
        enum_column_type(SuppressionReason, "suppression_reason", 24),
        nullable=False,
        server_default=SuppressionReason.manual.value,
    )

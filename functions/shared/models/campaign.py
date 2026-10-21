"""Campaign and CampaignContact models for Catalyst functions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceScopedMixin
from shared.models.enums import CampaignStatus, CampaignType, enum_column_type

if TYPE_CHECKING:
    from shared.models.contact import Contact


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "campaigns"

    type: Mapped[CampaignType] = mapped_column(
        enum_column_type(CampaignType, "campaign_type", 16), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        enum_column_type(CampaignStatus, "campaign_status", 16),
        nullable=False,
        default=CampaignStatus.draft,
        server_default=CampaignStatus.draft.value,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    contacts: Mapped[list["CampaignContact"]] = relationship(back_populates="campaign", passive_deletes=True)


class CampaignContact(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "campaign_contacts"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="contacts")
    contact: Mapped["Contact"] = relationship(back_populates="campaign_contacts")

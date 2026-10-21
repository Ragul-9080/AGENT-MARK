from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
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
    CampaignContactStatus,
    CampaignStatus,
    CampaignType,
    enum_column_type,
)

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.workspace import Workspace


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
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    workspace: Mapped[Workspace] = relationship(back_populates="campaigns")
    campaign_contacts: Mapped[list[CampaignContact]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", passive_deletes=True
    )


class CampaignContact(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "campaign_contacts"
    __table_args__ = (
        UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_contacts_campaign_contact"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[CampaignContactStatus] = mapped_column(
        enum_column_type(CampaignContactStatus, "campaign_contact_status", 16),
        nullable=False,
        default=CampaignContactStatus.pending,
        server_default=CampaignContactStatus.pending.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped[Campaign] = relationship(back_populates="campaign_contacts")
    contact: Mapped[Contact] = relationship(back_populates="campaign_contacts")

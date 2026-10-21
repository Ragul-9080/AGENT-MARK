"""Contact model for Catalyst functions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, WorkspaceScopedMixin

if TYPE_CHECKING:
    from shared.models.consent import Consent
    from shared.models.campaign import CampaignContact
    from shared.models.email import EmailMessage


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "phone", name="uq_contacts_workspace_phone"),
        UniqueConstraint("workspace_id", "email", name="uq_contacts_workspace_email"),
    )

    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="contacts")
    consents: Mapped[list["Consent"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", passive_deletes=True
    )
    campaign_contacts: Mapped[list["CampaignContact"]] = relationship(
        back_populates="contact", passive_deletes=True
    )
    email_messages: Mapped[list["EmailMessage"]] = relationship(
        back_populates="contact", passive_deletes=True
    )

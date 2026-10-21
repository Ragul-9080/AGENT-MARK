from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)

if TYPE_CHECKING:
    from app.models.campaign import CampaignContact
    from app.models.consent import Consent
    from app.models.email import EmailMessage
    from app.models.voice import Call
    from app.models.workspace import Workspace


class Contact(
    Base,
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    WorkspaceScopedMixin,
):
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

    workspace: Mapped[Workspace] = relationship(back_populates="contacts")
    consents: Mapped[list[Consent]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", passive_deletes=True
    )
    campaign_contacts: Mapped[list[CampaignContact]] = relationship(
        back_populates="contact", passive_deletes=True
    )
    calls: Mapped[list[Call]] = relationship(back_populates="contact", passive_deletes=True)
    email_messages: Mapped[list[EmailMessage]] = relationship(
        back_populates="contact", passive_deletes=True
    )

    @property
    def display_name(self) -> str:
        return self.name or self.phone or self.email or "Unnamed contact"

    @property
    def phone_value(self) -> str | None:
        return self.phone

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Contact id={self.id} name={self.name!r}>"

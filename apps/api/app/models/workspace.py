from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.contact import Contact
    from app.models.user import User


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata"
    )
    default_language: Mapped[str] = mapped_column(
        String(16), nullable=False, default="en-IN", server_default="en-IN"
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    users: Mapped[list[User]] = relationship(back_populates="workspace")
    contacts: Mapped[list[Contact]] = relationship(back_populates="workspace")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="workspace")

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WorkspaceScopedMixin,
)
from app.models.enums import (
    CallDirection,
    CallOutcome,
    CallSpeaker,
    Sentiment,
    enum_column_type,
)

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.contact import Contact


class Call(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "calls"

    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    direction: Mapped[CallDirection] = mapped_column(
        enum_column_type(CallDirection, "call_direction", 16), nullable=False
    )
    vobiz_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    outcome: Mapped[CallOutcome | None] = mapped_column(
        enum_column_type(CallOutcome, "call_outcome", 24), nullable=True
    )
    sentiment: Mapped[Sentiment | None] = mapped_column(
        enum_column_type(Sentiment, "call_sentiment", 16), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    campaign: Mapped[Campaign | None] = relationship()
    contact: Mapped[Contact | None] = relationship(back_populates="calls")
    turns: Mapped[list[CallTurn]] = relationship(
        back_populates="call", cascade="all, delete-orphan", passive_deletes=True
    )


class CallTurn(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "call_turns"

    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker: Mapped[CallSpeaker] = mapped_column(
        enum_column_type(CallSpeaker, "call_speaker", 16), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    started_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    call: Mapped[Call] = relationship(back_populates="turns")

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
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
    SeoAuditStatus,
    SeoIssueSeverity,
    SeoRecommendationStatus,
    enum_column_type,
)


class Website(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "websites"

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    verification_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_audit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audits: Mapped[list[SeoAudit]] = relationship(
        back_populates="website", cascade="all, delete-orphan", passive_deletes=True
    )


class SeoAudit(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "seo_audits"

    website_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[SeoAuditStatus] = mapped_column(
        enum_column_type(SeoAuditStatus, "seo_audit_status", 16),
        nullable=False,
        default=SeoAuditStatus.queued,
        server_default=SeoAuditStatus.queued.value,
    )
    health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_crawled: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    website: Mapped[Website] = relationship(back_populates="audits")
    issues: Mapped[list[SeoIssue]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", passive_deletes=True
    )
    recommendations: Mapped[list[SeoRecommendation]] = relationship(
        back_populates="audit", cascade="all, delete-orphan", passive_deletes=True
    )


class SeoIssue(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "seo_issues"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seo_audits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[SeoIssueSeverity] = mapped_column(
        enum_column_type(SeoIssueSeverity, "seo_issue_severity", 12), nullable=False
    )
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    audit: Mapped[SeoAudit] = relationship(back_populates="issues")


class SeoRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "seo_recommendations"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("seo_audits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    impact: Mapped[str] = mapped_column(String(16), nullable=False)
    effort: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SeoRecommendationStatus] = mapped_column(
        enum_column_type(SeoRecommendationStatus, "seo_recommendation_status", 16),
        nullable=False,
        default=SeoRecommendationStatus.proposed,
        server_default=SeoRecommendationStatus.proposed.value,
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    llm_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_input: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    audit: Mapped[SeoAudit] = relationship(back_populates="recommendations")

"""Shared enums for all Catalyst functions.

Adapted from apps/api/app/models/enums.py. Uses StrEnum for portability.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class ConsentChannel(StrEnum):
    voice = "voice"
    email = "email"


class ConsentStatus(StrEnum):
    granted = "granted"
    revoked = "revoked"


class SuppressionReason(StrEnum):
    dnd = "dnd"
    unsubscribe = "unsubscribe"
    bounce = "bounce"
    complaint = "complaint"
    manual = "manual"


class CampaignType(StrEnum):
    voice = "voice"
    email = "email"


class CampaignStatus(StrEnum):
    draft = "draft"
    scheduled = "scheduled"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class CampaignContactStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"
    failed = "failed"


class EmailMessageStatus(StrEnum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    bounced = "bounced"
    complained = "complained"
    failed = "failed"


class EmailEventType(StrEnum):
    delivered = "delivered"
    open = "open"
    click = "click"
    bounce = "bounce"
    complaint = "complaint"
    reply = "reply"
    unsubscribe = "unsubscribe"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    dead_letter = "dead_letter"


class EventModule(StrEnum):
    system = "system"
    voice = "voice"
    email = "email"
    seo = "seo"

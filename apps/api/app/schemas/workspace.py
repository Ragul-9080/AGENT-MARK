from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class WorkspaceUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    default_language: str | None = Field(default=None, max_length=16)
    settings: dict[str, Any] | None = None


class MemberOut(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    is_active: bool

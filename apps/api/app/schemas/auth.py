from __future__ import annotations

import uuid
from typing import Any

from pydantic import EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class RegisterRequest(ORMModel):
    workspace_name: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value


class LoginRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(ORMModel):
    refresh_token: str = Field(min_length=1)


class WorkspaceOut(ORMModel):
    id: uuid.UUID
    name: str
    timezone: str
    default_language: str
    settings: dict[str, Any] = Field(default_factory=dict)


class UserOut(ORMModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    email: EmailStr
    name: str
    role: UserRole


class AuthResponse(ORMModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserOut
    workspace: WorkspaceOut


class MeResponse(ORMModel):
    user: UserOut
    workspace: WorkspaceOut

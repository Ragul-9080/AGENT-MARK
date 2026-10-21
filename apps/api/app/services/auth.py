from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_token_pair, decode_token, hash_password, verify_password
from app.models.enums import EventModule, UserRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import AuthResponse, MeResponse, RegisterRequest, UserOut, WorkspaceOut
from app.services.events import record_event


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _auth_response(user: User, workspace: Workspace) -> AuthResponse:
    tokens = create_token_pair(user.id, workspace.id, user.role.value)
    return AuthResponse(
        **tokens,
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut.model_validate(workspace),
    )


def register(db: Session, data: RegisterRequest) -> AuthResponse:
    email = normalize_email(str(data.email))
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AppError(
            409,
            "email_in_use",
            "An account with that email already exists. Try signing in.",
        )

    start, end = settings.default_calling_window.split("-", 1)
    workspace = Workspace(
        name=data.workspace_name.strip(),
        timezone="Asia/Kolkata",
        default_language="en-IN",
        settings={
            "calling_hours": {"start": start, "end": end, "timezone": "contact"},
            "recording_enabled": False,
            "sender": {},
        },
    )
    db.add(workspace)
    db.flush()

    user = User(
        workspace_id=workspace.id,
        email=email,
        name=data.name.strip(),
        password_hash=hash_password(data.password),
        role=UserRole.owner,
    )
    db.add(user)
    db.flush()

    record_event(
        db,
        workspace_id=workspace.id,
        source_module=EventModule.system,
        type="workspace.created",
        payload={"workspace_name": workspace.name},
    )

    return _auth_response(user, workspace)


def login(db: Session, email: str, password: str) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AppError(
            401,
            "invalid_credentials",
            "That email and password combination is not correct.",
        )

    user.last_login_at = datetime.now(UTC)
    workspace = db.get(Workspace, user.workspace_id)
    if workspace is None:
        raise AppError(401, "invalid_credentials", "This account is not available.")

    return _auth_response(user, workspace)


def refresh(db: Session, refresh_token: str) -> AuthResponse:
    payload = decode_token(refresh_token, "refresh")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        workspace_id = uuid.UUID(str(payload["ws"]))
    except (KeyError, ValueError) as exc:
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.") from exc

    user = db.get(User, user_id)
    workspace = db.get(Workspace, workspace_id)
    if user is None or workspace is None or not user.is_active or user.workspace_id != workspace_id:
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.")

    return _auth_response(user, workspace)


def me(user: User) -> MeResponse:
    return MeResponse(
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut.model_validate(user.workspace),
    )

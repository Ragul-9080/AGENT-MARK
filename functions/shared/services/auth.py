"""Auth service for Catalyst functions.

Register, login, password hashing, JWT tokens.
Adapted from apps/api/app/services/auth.py.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.core.errors import AppError
from shared.core.security import create_token_pair, hash_password, verify_password
from shared.models.user import User
from shared.models.workspace import Workspace


def create_user_and_workspace(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    workspace_name: str,
) -> tuple[User, Workspace]:
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AppError(409, "user_exists", "An account with this email already exists.")

    workspace = Workspace(name=workspace_name)
    db.add(workspace)
    db.flush()

    user = User(
        workspace_id=workspace.id,
        email=email,
        name=name,
        password_hash=hash_password(password),
        role="owner",
    )
    db.add(user)
    db.flush()
    return user, workspace


def authenticate_user(
    db: Session, email: str, password: str
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        raise AppError(401, "invalid_credentials", "Invalid email or password.")
    if not verify_password(password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid email or password.")
    return user

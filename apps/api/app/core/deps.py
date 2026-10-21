from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import decode_token
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "unauthorized", "Please sign in to continue.")

    payload = decode_token(credentials.credentials, "access")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        workspace_id = uuid.UUID(str(payload["ws"]))
    except (KeyError, ValueError) as exc:
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.") from exc

    user = db.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or user.workspace_id != workspace_id
        or user.role != payload.get("role")
    ):
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = set(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError(403, "forbidden", "You do not have permission to do that.")
        return user

    return dependency


OwnerOrAdmin = Annotated[User, Depends(require_roles(UserRole.owner, UserRole.admin))]

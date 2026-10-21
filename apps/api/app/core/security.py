from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import AppError

TokenType = Literal["access", "refresh"]

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _create_token(
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    role: str,
    token_type: TokenType,
    lifetime: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ws": str(workspace_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_token_pair(user_id: uuid.UUID, workspace_id: uuid.UUID, role: str) -> dict[str, Any]:
    access = _create_token(
        user_id,
        workspace_id,
        role,
        "access",
        timedelta(minutes=settings.access_token_minutes),
    )
    refresh = _create_token(
        user_id,
        workspace_id,
        role,
        "refresh",
        timedelta(days=settings.refresh_token_days),
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
    }


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Your session expired. Please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.") from exc

    if payload.get("type") != expected_type:
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.")

    try:
        uuid.UUID(str(payload["sub"]))
        uuid.UUID(str(payload["ws"]))
    except (KeyError, ValueError) as exc:
        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.") from exc

    return payload

"""Security utilities for Catalyst functions: password hashing and JWT tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher

from shared.core.config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        return False


def create_token_pair(user_id: uuid.UUID, workspace_id: uuid.UUID, role: str) -> dict[str, str]:
    now = datetime.now(UTC)
    access = {
        "sub": str(user_id),
        "ws": str(workspace_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    refresh = {
        "sub": str(user_id),
        "ws": str(workspace_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_days),
    }
    return {
        "access_token": jwt.encode(access, settings.jwt_secret, algorithm=settings.jwt_algorithm),
        "refresh_token": jwt.encode(refresh, settings.jwt_secret, algorithm=settings.jwt_algorithm),
        "access_token_expires_at": (now + timedelta(minutes=settings.access_token_minutes)).isoformat(),
    }


def decode_token(token: str, token_type: str = "access") -> dict[str, object]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        from shared.core.errors import AppError

        raise AppError(401, "token_expired", "Your session has expired. Please sign in.") from exc
    except jwt.InvalidTokenError as exc:
        from shared.core.errors import AppError

        raise AppError(401, "invalid_token", "Your session is not valid. Please sign in.") from exc
    return payload

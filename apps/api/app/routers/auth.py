from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, DbSession
from app.core.rate_limit import enforce_auth_rate_limit
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    return auth_service.register(db, payload)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    return auth_service.login(db, str(payload.email), payload.password)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
def refresh(payload: RefreshRequest, db: DbSession) -> AuthResponse:
    return auth_service.refresh(db, payload.refresh_token)


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    return auth_service.me(user)

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, new_request_id, request_id_var
from app.routers import (
    auth,
    campaigns,
    contacts,
    dashboard,
    email,
    events,
    health,
    jobs,
    suppressions,
    webhooks,
    workspace,
)

logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    settings.validate_runtime()
    logger.info("API starting in %s mode", settings.app_env)
    yield
    logger.info("API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.api_version,
        description=(
            "Common API for the Agentic Marketing Platform. All data is scoped to a "
            "workspace; module workers use the same consent, suppression and event services."
        ),
        lifespan=lifespan,
    )

    install_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "%s %s failed after %.1fms", request.method, request.url.path, duration_ms
            )
            raise
        else:
            duration_ms = (time.perf_counter() - started) * 1000
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            logger.info(
                "%s %s -> %s in %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            request_id_var.reset(token)

    api_routers = [
        health.router,
        auth.router,
        workspace.router,
        contacts.router,
        suppressions.router,
        campaigns.router,
        email.router,
        events.router,
        dashboard.router,
        jobs.router,
        webhooks.router,
    ]
    for router in api_routers:
        app.include_router(router)

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.api_version,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()

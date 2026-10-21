"""Application settings for Catalyst functions.

Loaded from environment variables. Catalyst injects env vars via
catalyst-config.json (deployment.env_variables) or the Catalyst console.
Never hardcode secrets here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Agentic Marketing Platform"
    app_env: str = "development"
    log_level: str = "INFO"
    api_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ama"
    redis_url: str = ""

    jwt_secret: str = "local-development-only-change-me"  # noqa: S105
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    auth_rate_limit_per_minute: int = 20

    public_base_url: str = "https://catalyst.zoho.com"
    dashboard_origin: str = ""

    sarvam_api_key: str = ""
    sarvam_stt_model: str = "saaras:v3"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_default_language: str = "hi-IN"
    sarvam_default_speaker: str = "anushka"

    vobiz_auth_id: str = ""
    vobiz_auth_token: str = ""
    vobiz_webhook_secret: str = ""
    vobiz_phone_number: str = ""

    email_provider: str = "console"
    email_from_name: str = ""
    email_from_address: str = ""
    email_webhook_secret: str = ""
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    ses_configuration_set: str = ""

    default_calling_window: str = "09:00-21:00"
    dnd_registry_provider: str = ""
    contact_import_max_rows: int = 5000
    contact_import_max_bytes: int = 5 * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "staging"}

    def validate_runtime(self) -> None:
        if self.is_production and "change-me" in self.jwt_secret:
            raise RuntimeError(
                "JWT_SECRET must be replaced with a strong random value outside development."
            )
        if self.access_token_minutes < 1 or self.refresh_token_days < 1:
            raise RuntimeError("Token lifetimes must be positive.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

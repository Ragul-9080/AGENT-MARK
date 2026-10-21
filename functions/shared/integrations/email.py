"""Email provider adapters for Catalyst functions.

Console provider logs instead of sending (safe for local dev/CI).
SES provider calls Amazon SES when credentials are configured.
Neither logs PII (recipient address, subject, body).
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any

try:  # boto3 is only required for the SES provider
    import boto3  # type: ignore[import-not-found]
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - SES path only
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception

from shared.core.config import settings

logger = logging.getLogger("shared.integrations.email")


class EmailProviderError(RuntimeError):
    """Raised when an email provider cannot complete a send."""


class EmailProvider(ABC):
    """Abstract email provider. Never logs PII."""

    @abstractmethod
    def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str | None,
        body_text: str | None,
    ) -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class ConsoleEmailProvider(EmailProvider):
    """Logs the send instead of delivering. Safe default."""

    def name(self) -> str:
        return "console"

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str | None,
        body_text: str | None,
    ) -> str:
        message_id = f"console-{uuid.uuid4()}"
        logger.info(
            "email.send provider=console message_id=%s to=*** subject_len=%d has_html=%d has_text=%d",
            message_id,
            len(subject or ""),
            bool(body_html),
            bool(body_text),
        )
        return message_id


class SESEmailProvider(EmailProvider):
    """Amazon SES provider."""

    def __init__(self) -> None:
        if boto3 is None:  # pragma: no cover
            raise EmailProviderError("boto3 is not installed; install it to use the SES provider")
        if not settings.email_from_address:
            raise EmailProviderError("EMAIL_FROM_ADDRESS is required for SES provider")
        if not settings.aws_region:
            raise EmailProviderError("AWS_REGION is required for SES provider")
        self._ses = boto3.client(
            "ses",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        self._from_address = settings.email_from_address
        self._from_name = settings.email_from_name or ""
        self._configuration_set = settings.ses_configuration_set or None

    def name(self) -> str:
        return "ses"

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str | None,
        body_text: str | None,
    ) -> str:
        source = f"{self._from_name} <{self._from_address}>" if self._from_name else self._from_address

        message: dict[str, Any] = {"Subject": {"Data": subject, "Charset": "UTF-8"}}
        body: dict[str, Any] = {}
        if body_text:
            body["Text"] = {"Data": body_text, "Charset": "UTF-8"}
        if body_html:
            body["Html"] = {"Data": body_html, "Charset": "UTF-8"}
        message["Body"] = body

        kwargs: dict[str, Any] = {
            "Source": source,
            "Destination": {"ToAddresses": [to]},
            "Message": message,
        }
        if self._configuration_set:
            kwargs["ConfigurationSetName"] = self._configuration_set

        try:
            response = self._ses.send_email(**kwargs)
        except (BotoCoreError, ClientError) as exc:
            logger.error("email.send provider=ses to=*** error=%s", type(exc).__name__)
            raise EmailProviderError(f"SES send failed: {exc}") from exc

        message_id = response.get("MessageId")
        if not message_id:
            raise EmailProviderError("SES did not return a MessageId")
        logger.info(
            "email.send provider=ses message_id=%s to=*** subject_len=%d",
            message_id,
            len(subject or ""),
        )
        return message_id


def get_email_provider() -> EmailProvider:
    """Return the configured email provider."""
    provider = (settings.email_provider or "console").strip().lower()
    if provider == "ses":
        return SESEmailProvider()
    return ConsoleEmailProvider()

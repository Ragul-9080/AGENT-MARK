"""Catalyst function: voice.

Phase 1 stub: health checks only. Outbound calling lands in Phase 2 behind
Vobiz + Sarvam adapters. Never simulates outbound calls (no false claims).
Entry point for Catalyst: handler(context, request).
"""

from __future__ import annotations

import json
import os
from typing import Any


def _response(status_code: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": body if isinstance(body, str) else json.dumps(body),
    }


def _configured(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def handler(context: Any, request: Any) -> dict[str, Any]:
    """Catalyst entry point for the voice function."""

    method = (request.get("method") if isinstance(request, dict) else "GET").upper()
    path = request.get("path", "/") if isinstance(request, dict) else "/"

    if method == "GET" and path == "/":
        return _response(200, {
            "service": "voice",
            "phase": "phase-1-stub",
            "implemented": False,
            "integrations": {
                "vobiz": _configured("VOBIZ_AUTH_ID") and _configured("VOBIZ_AUTH_TOKEN"),
                "sarvam": _configured("SARVAM_API_KEY"),
            },
            "notes": "Call handling lands in Phase 2. Health endpoints are live.",
        })

    if method == "GET" and path == "/health":
        return _response(200, {"status": "ok", "service": "voice", "phase": "phase-1-stub"})

    if method == "POST" and path == "/calls":
        # Deliberately unimplemented: a stub must never simulate outbound calls.
        return _response(501, {"error": {"type": "not_implemented", "message": "Outbound calling is not implemented yet. Voice lands in Phase 2."}})

    return _response(404, {"error": {"type": "not_found", "message": "Voice endpoint not found."}})

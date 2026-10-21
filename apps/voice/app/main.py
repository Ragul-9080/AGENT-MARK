"""Voice service stub for the Agentic Marketing Platform.

Phase 1 scope: this service exists so the platform has a place to put real-time
call handling, and so `docker compose up` brings up every service. It does not
place calls yet.

Phase 2 will add Vobiz call control and Sarvam speech in and speech out here,
behind the same consent, suppression and calling-window rules the API already
enforces. Until those adapters exist, the only safe behaviour is to answer
health checks and refuse everything else.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Agentic Marketing Voice",
    version="0.1.0",
    description="Voice service stub. Call handling is implemented in Phase 2.",
)

PHASE = "phase-1-stub"


def _configured(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


@app.get("/", tags=["meta"])
def root() -> dict[str, object]:
    return {
        "service": "voice",
        "phase": PHASE,
        "implemented": False,
        "integrations": {
            "vobiz": _configured("VOBIZ_AUTH_ID") and _configured("VOBIZ_AUTH_TOKEN"),
            "sarvam": _configured("SARVAM_API_KEY"),
        },
        "notes": "Call handling lands in Phase 2. Health endpoints are live.",
    }


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "voice", "phase": PHASE}


@app.post("/calls", tags=["calls"], status_code=501)
def place_call() -> None:
    # Deliberately unimplemented: a stub must never simulate outbound calls
    # because that would create false claims about what the platform did.
    raise HTTPException(
        status_code=501,
        detail="Outbound calling is not implemented yet. Voice lands in Phase 2.",
    )

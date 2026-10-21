from __future__ import annotations

import hashlib
import hmac
import uuid

from app.models.enums import JobStatus, UserRole
from app.models.job import WebhookDelivery
from app.models.user import User
from app.services.jobs import create_job
from app.services.webhooks import workspace_webhook_token
from app.workers.tasks import ping_job
from fastapi.testclient import TestClient
from sqlalchemy import select


def test_jobs_can_be_listed_and_fetched(
    client: TestClient, auth_headers: dict, account: dict, db
) -> None:
    job = create_job(
        db,
        workspace_id=uuid.UUID(account["workspace"]["id"]),
        type="system.test",
        payload={"hello": "world"},
    )
    db.commit()

    listing = client.get("/jobs", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["status"] == "queued"

    fetched = client.get(f"/jobs/{job.id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["payload"] == {"hello": "world"}

    filtered = client.get("/jobs?status=succeeded", headers=auth_headers)
    assert filtered.json()["total"] == 0


def test_jobs_are_isolated(
    client: TestClient, auth_headers: dict, other_headers: dict, account: dict, db
) -> None:
    job = create_job(
        db,
        workspace_id=uuid.UUID(account["workspace"]["id"]),
        type="system.test",
        payload={},
    )
    db.commit()

    assert client.get("/jobs", headers=other_headers).json()["total"] == 0
    assert client.get(f"/jobs/{job.id}", headers=other_headers).status_code == 404
    assert client.get(f"/jobs/{uuid.uuid4()}", headers=auth_headers).status_code == 404


def test_ping_job_enqueues(client: TestClient, auth_headers: dict, monkeypatch) -> None:
    calls: list[str] = []

    def fake_delay(job_id: str) -> None:
        calls.append(job_id)

    monkeypatch.setattr(ping_job, "delay", fake_delay)

    response = client.post("/jobs/ping", headers=auth_headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["type"] == "system.ping"
    assert body["status"] == "queued"
    assert calls == [body["id"]]


def test_ping_job_marks_failed_when_queue_is_unavailable(
    client: TestClient, auth_headers: dict, monkeypatch
) -> None:
    def broken_delay(job_id: str) -> None:
        raise RuntimeError("broker down")

    monkeypatch.setattr(ping_job, "delay", broken_delay)

    response = client.post("/jobs/ping", headers=auth_headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"

    listing = client.get("/jobs?status=failed", headers=auth_headers).json()
    assert listing["total"] == 1
    assert listing["items"][0]["error"] == "Queue unavailable"


def test_members_cannot_enqueue_jobs(client: TestClient, account: dict, db) -> None:
    from app.core.security import hash_password

    member = User(
        workspace_id=uuid.UUID(account["workspace"]["id"]),
        email="jobs-member@example.com",
        name="Jobs Member",
        password_hash=hash_password("member password"),
        role=UserRole.member,
    )
    db.add(member)
    db.commit()

    login = client.post(
        "/auth/login", json={"email": "jobs-member@example.com", "password": "member password"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.post("/jobs/ping", headers=headers).status_code == 403


def test_webhook_requires_a_valid_workspace_token(client: TestClient, account: dict, db) -> None:
    workspace_id = account["workspace"]["id"]

    missing = client.post(f"/webhooks/vobiz?workspace_id={workspace_id}&token=nope")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "invalid_webhook_token"

    unknown_provider = client.post(
        f"/webhooks/twilio?workspace_id={workspace_id}&token={workspace_webhook_token(uuid.UUID(workspace_id))}"
    )
    assert unknown_provider.status_code == 404

    unknown_workspace = client.post(
        f"/webhooks/vobiz?workspace_id={uuid.uuid4()}&token={workspace_webhook_token(uuid.uuid4())}"
    )
    assert unknown_workspace.status_code == 401


def test_webhook_stores_unverified_delivery_when_no_secret(
    client: TestClient, account: dict, db
) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    response = client.post(
        f"/webhooks/vobiz?workspace_id={workspace_id}&token={workspace_webhook_token(workspace_id)}",
        json={"Event": "call.completed", "call_id": "abc"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_webhook_signature"

    delivery = db.scalar(select(WebhookDelivery))
    assert delivery is not None
    assert delivery.signature_valid is False
    assert delivery.event_type == "call.completed"
    assert delivery.error == "verification_not_configured"
    assert delivery.payload["call_id"] == "abc"


def test_webhook_accepts_a_valid_vobiz_signature(
    client: TestClient, account: dict, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "vobiz_webhook_secret", "vobiz-secret")
    workspace_id = uuid.UUID(account["workspace"]["id"])
    body = b'{"Event": "call.completed", "call_id": "abc"}'
    signature = hmac.new(b"vobiz-secret", body, hashlib.sha256).hexdigest()

    response = client.post(
        f"/webhooks/vobiz?workspace_id={workspace_id}&token={workspace_webhook_token(workspace_id)}",
        content=body,
        headers={
            "content-type": "application/json",
            "x-vobiz-signature-v3": f"sha256={signature}",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "accepted"


def test_webhook_rejects_a_bad_vobiz_signature(
    client: TestClient, account: dict, monkeypatch, db
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "vobiz_webhook_secret", "vobiz-secret")
    workspace_id = uuid.UUID(account["workspace"]["id"])

    response = client.post(
        f"/webhooks/vobiz?workspace_id={workspace_id}&token={workspace_webhook_token(workspace_id)}",
        content=b'{"Event": "call.completed"}',
        headers={
            "content-type": "application/json",
            "x-vobiz-signature-v3": "sha256=deadbeef",
        },
    )
    assert response.status_code == 401
    delivery = db.scalar(select(WebhookDelivery))
    assert delivery is not None
    assert delivery.signature_valid is False
    assert delivery.error == "invalid_signature"


def test_webhook_accepts_form_encoded_email_callback(
    client: TestClient, account: dict, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "email_webhook_secret", "email-secret")
    workspace_id = uuid.UUID(account["workspace"]["id"])
    body = b"notificationType=Delivery&messageId=xyz"
    signature = hmac.new(b"email-secret", body, hashlib.sha256).hexdigest()

    response = client.post(
        f"/webhooks/email?workspace_id={workspace_id}&token={workspace_webhook_token(workspace_id)}",
        content=body,
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "x-webhook-signature": signature,
        },
    )
    assert response.status_code == 200, response.text


def test_webhook_payload_size_is_limited(client: TestClient, account: dict) -> None:
    workspace_id = uuid.UUID(account["workspace"]["id"])
    response = client.post(
        f"/webhooks/vobiz?workspace_id={workspace_id}&token={workspace_webhook_token(workspace_id)}",
        content=b"x" * (1024 * 1024 + 1),
        headers={"content-type": "text/plain"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_job_status_enum_values_are_stable() -> None:
    assert JobStatus.dead_letter.value == "dead_letter"
    assert JobStatus.queued.value == "queued"

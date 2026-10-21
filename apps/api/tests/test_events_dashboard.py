from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models.email import EmailMessage
from app.models.enums import CallDirection, SeoAuditStatus
from app.models.seo import SeoAudit, Website
from app.models.voice import Call
from fastapi.testclient import TestClient


def test_event_timeline_and_filters(client: TestClient, auth_headers: dict, create_contact) -> None:
    contact = create_contact()
    client.patch(f"/contacts/{contact['id']}", headers=auth_headers, json={"name": "Updated"})

    # Registration itself writes a workspace.created event.
    events = client.get("/events", headers=auth_headers).json()
    assert events["total"] == 3
    types = [item["type"] for item in events["items"]]
    assert types[0] == "contact.updated"
    assert {"contact.created", "workspace.created"} <= set(types)

    only_created = client.get("/events?type=contact.created", headers=auth_headers).json()
    assert only_created["total"] == 1
    assert only_created["items"][0]["payload"]["source"] == "manual"

    by_contact = client.get(f"/events?contact_id={contact['id']}", headers=auth_headers).json()
    assert by_contact["total"] == 2

    by_module = client.get("/events?module=system", headers=auth_headers).json()
    assert by_module["total"] == 3

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    none_in_future = client.get(
        "/events", headers=auth_headers, params={"date_from": future}
    ).json()
    assert none_in_future["total"] == 0

    paged = client.get("/events?limit=1&offset=1", headers=auth_headers).json()
    assert len(paged["items"]) == 1
    assert paged["total"] == 3


def test_events_are_isolated(client: TestClient, other_headers: dict, create_contact) -> None:
    created = create_contact()
    other_events = client.get("/events", headers=other_headers).json()
    assert other_events["total"] == 1
    assert other_events["items"][0]["type"] == "workspace.created"
    assert other_events["items"][0]["contact_id"] is None

    by_contact = client.get(f"/events?contact_id={created['id']}", headers=other_headers).json()
    assert by_contact["total"] == 0


def test_dashboard_summary_counts_only_own_workspace(
    client: TestClient, auth_headers: dict, other_headers: dict, account: dict, db, create_contact
) -> None:
    create_contact()
    campaign = client.post(
        "/campaigns", headers=auth_headers, json={"type": "voice", "name": "Live"}
    ).json()
    client.post(f"/campaigns/{campaign['id']}/start", headers=auth_headers)

    workspace_id = uuid.UUID(account["workspace"]["id"])
    contact_id = uuid.UUID(client.get("/contacts", headers=auth_headers).json()["items"][0]["id"])

    db.add(
        Call(
            workspace_id=workspace_id,
            contact_id=contact_id,
            direction=CallDirection.outbound,
            duration_s=42,
        )
    )
    db.add(
        EmailMessage(
            workspace_id=workspace_id,
            contact_id=contact_id,
            subject="Hello",
            body_html="<p>Hello</p>",
            sent_at=datetime.now(UTC),
        )
    )
    website = Website(workspace_id=workspace_id, url="https://example.com")
    db.add(website)
    db.flush()
    db.add(
        SeoAudit(
            workspace_id=workspace_id,
            website_id=website.id,
            status=SeoAuditStatus.completed,
            health_score=87,
            completed_at=datetime.now(UTC),
        )
    )
    db.commit()

    summary = client.get("/dashboard/summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["contacts"] == 1
    assert body["calls"] == 1
    assert body["emails_sent"] == 1
    assert body["latest_seo_score"] == 87
    assert body["running_campaigns"] == 1
    assert body["active_campaigns"][0]["id"] == campaign["id"]
    assert body["recent_events"]

    other = client.get("/dashboard/summary", headers=other_headers).json()
    assert other["contacts"] == 0
    assert other["calls"] == 0
    assert other["emails_sent"] == 0
    assert other["latest_seo_score"] is None
    assert other["running_campaigns"] == 0
    assert other["active_campaigns"] == []
    assert [event["type"] for event in other["recent_events"]] == ["workspace.created"]

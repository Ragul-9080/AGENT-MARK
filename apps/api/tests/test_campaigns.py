from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models.campaign import Campaign
from app.services.campaigns import promote_due_campaigns
from fastapi.testclient import TestClient
from sqlalchemy import select


def _create_campaign(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {"type": "voice", "name": "Diwali Calling"}
    payload.update(overrides)
    response = client.post("/campaigns", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_campaign_crud_and_filters(client: TestClient, auth_headers: dict) -> None:
    voice = _create_campaign(client, auth_headers)
    email = _create_campaign(client, auth_headers, type="email", name="Newsletter")

    assert voice["status"] == "draft"
    listing = client.get("/campaigns", headers=auth_headers).json()
    assert listing["total"] == 2

    by_type = client.get("/campaigns?type=email", headers=auth_headers).json()
    assert by_type["total"] == 1
    assert by_type["items"][0]["id"] == email["id"]

    by_status = client.get("/campaigns?status=running", headers=auth_headers).json()
    assert by_status["total"] == 0

    updated = client.patch(
        f"/campaigns/{voice['id']}",
        headers=auth_headers,
        json={"name": "Diwali Calling v2", "settings": {"disclosure": True}},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Diwali Calling v2"
    assert updated.json()["settings"] == {"disclosure": True}

    deleted = client.delete(f"/campaigns/{email['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/campaigns", headers=auth_headers).json()["total"] == 1


def test_campaign_state_machine(client: TestClient, auth_headers: dict) -> None:
    campaign = _create_campaign(client, auth_headers)
    campaign_id = campaign["id"]

    started = client.post(f"/campaigns/{campaign_id}/start", headers=auth_headers)
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    cannot_start_again = client.post(f"/campaigns/{campaign_id}/start", headers=auth_headers)
    assert cannot_start_again.status_code == 409
    assert cannot_start_again.json()["error"]["code"] == "invalid_campaign_transition"

    paused = client.post(f"/campaigns/{campaign_id}/pause", headers=auth_headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    cannot_pause_twice = client.post(f"/campaigns/{campaign_id}/pause", headers=auth_headers)
    assert cannot_pause_twice.status_code == 409

    resumed = client.post(f"/campaigns/{campaign_id}/resume", headers=auth_headers)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"

    stopped = client.post(f"/campaigns/{campaign_id}/stop", headers=auth_headers)
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "completed"

    cannot_restart = client.post(f"/campaigns/{campaign_id}/start", headers=auth_headers)
    assert cannot_restart.status_code == 409

    events = client.get("/events?type=campaign.started", headers=auth_headers).json()
    assert events["total"] == 1

    # Completed campaigns are terminal and can be cleaned up.
    deleted = client.delete(f"/campaigns/{campaign_id}", headers=auth_headers)
    assert deleted.status_code == 204


def test_campaign_resume_requires_paused(client: TestClient, auth_headers: dict) -> None:
    campaign = _create_campaign(client, auth_headers)
    assert (
        client.post(f"/campaigns/{campaign['id']}/resume", headers=auth_headers).status_code == 409
    )
    assert (
        client.post(f"/campaigns/{campaign['id']}/pause", headers=auth_headers).status_code == 409
    )


def test_scheduled_campaign_is_promoted_when_due(
    client: TestClient, auth_headers: dict, db
) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    campaign = _create_campaign(
        client, auth_headers, scheduled_at=future.isoformat(), name="Scheduled"
    )

    scheduled = client.post(f"/campaigns/{campaign['id']}/start", headers=auth_headers)
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "scheduled"

    stored = db.scalar(select(Campaign).where(Campaign.id == uuid.UUID(campaign["id"])))
    assert stored is not None
    stored.scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    promoted = promote_due_campaigns(db)
    db.commit()
    assert [str(item) for item in promoted] == [campaign["id"]]

    refreshed = client.get(f"/campaigns/{campaign['id']}", headers=auth_headers).json()
    assert refreshed["status"] == "running"


def test_running_campaign_cannot_be_edited_or_deleted(
    client: TestClient, auth_headers: dict
) -> None:
    campaign = _create_campaign(client, auth_headers)
    client.post(f"/campaigns/{campaign['id']}/start", headers=auth_headers)

    update = client.patch(
        f"/campaigns/{campaign['id']}", headers=auth_headers, json={"name": "Nope"}
    )
    assert update.status_code == 409
    assert update.json()["error"]["code"] == "campaign_running"

    delete = client.delete(f"/campaigns/{campaign['id']}", headers=auth_headers)
    assert delete.status_code == 409


def test_campaign_recipients(client: TestClient, auth_headers: dict, create_contact) -> None:
    first = create_contact()
    second = create_contact(name="Second", phone="+919876500701", email="second@example.com")
    missing = str(uuid.uuid4())
    campaign = _create_campaign(client, auth_headers)

    added = client.post(
        f"/campaigns/{campaign['id']}/contacts",
        headers=auth_headers,
        json={"contact_ids": [first["id"], second["id"], first["id"], missing]},
    )
    assert added.status_code == 200, added.text
    assert added.json() == {"added": 2, "skipped": 0, "missing": 1}

    again = client.post(
        f"/campaigns/{campaign['id']}/contacts",
        headers=auth_headers,
        json={"contact_ids": [first["id"], second["id"], missing]},
    )
    assert again.status_code == 200
    assert again.json() == {"added": 0, "skipped": 2, "missing": 1}

    recipients = client.get(f"/campaigns/{campaign['id']}/contacts", headers=auth_headers).json()
    assert recipients["total"] == 2
    assert recipients["items"][0]["contact"]["id"] in {first["id"], second["id"]}
    assert recipients["items"][0]["status"] == "pending"

    client.post(f"/campaigns/{campaign['id']}/start", headers=auth_headers)
    locked = client.post(
        f"/campaigns/{campaign['id']}/contacts",
        headers=auth_headers,
        json={"contact_ids": [first["id"]]},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "campaign_not_editable"


def test_campaigns_are_isolated_between_workspaces(
    client: TestClient, auth_headers: dict, other_headers: dict, create_contact
) -> None:
    campaign = _create_campaign(client, auth_headers)
    contact = create_contact()

    assert client.get("/campaigns", headers=other_headers).json()["total"] == 0
    assert client.get(f"/campaigns/{campaign['id']}", headers=other_headers).status_code == 404
    assert (
        client.patch(
            f"/campaigns/{campaign['id']}", headers=other_headers, json={"name": "x"}
        ).status_code
        == 404
    )
    assert (
        client.post(f"/campaigns/{campaign['id']}/start", headers=other_headers).status_code == 404
    )
    assert client.delete(f"/campaigns/{campaign['id']}", headers=other_headers).status_code == 404
    assert (
        client.get(f"/campaigns/{campaign['id']}/contacts", headers=other_headers).status_code
        == 404
    )

    # The other workspace cannot attach its own contact to this campaign.
    assert (
        client.post(
            f"/campaigns/{campaign['id']}/contacts",
            headers=other_headers,
            json={"contact_ids": [contact["id"]]},
        ).status_code
        == 404
    )


def test_unknown_campaign_returns_404(client: TestClient, auth_headers: dict) -> None:
    missing = uuid.uuid4()
    assert client.get(f"/campaigns/{missing}", headers=auth_headers).status_code == 404
    assert client.post(f"/campaigns/{missing}/start", headers=auth_headers).status_code == 404

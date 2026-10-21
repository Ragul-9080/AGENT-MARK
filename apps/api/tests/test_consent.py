from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_consent_gate_requires_recorded_consent(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    contact = create_contact()

    eligibility = client.get(f"/contacts/{contact['id']}/eligibility", headers=auth_headers)
    assert eligibility.status_code == 200
    body = eligibility.json()
    assert body["voice"]["allowed"] is False
    assert body["voice"]["reason"] == "no_consent"
    assert body["email"]["reason"] == "no_consent"

    granted = client.put(
        f"/contacts/{contact['id']}/consents/voice",
        headers=auth_headers,
        json={"status": "granted", "proof": "web form 2026-10-19"},
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["status"] == "granted"
    assert granted.json()["proof"] == "web form 2026-10-19"

    email_consent = client.put(
        f"/contacts/{contact['id']}/consents/email",
        headers=auth_headers,
        json={"status": "granted"},
    )
    assert email_consent.status_code == 200

    allowed = client.get(f"/contacts/{contact['id']}/eligibility", headers=auth_headers).json()
    assert allowed["voice"]["allowed"] is True
    assert allowed["email"]["allowed"] is True
    assert allowed["voice"]["message"] == "Ready to contact."

    consents = client.get(f"/contacts/{contact['id']}/consents", headers=auth_headers)
    assert consents.status_code == 200
    assert {item["channel"] for item in consents.json()} == {"voice", "email"}

    events = client.get(f"/contacts/{contact['id']}/events", headers=auth_headers).json()
    assert "consent.granted" in {item["type"] for item in events["items"]}


def test_revoked_consent_blocks_contact(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    contact = create_contact()
    client.put(
        f"/contacts/{contact['id']}/consents/voice",
        headers=auth_headers,
        json={"status": "granted"},
    )
    revoked = client.put(
        f"/contacts/{contact['id']}/consents/voice",
        headers=auth_headers,
        json={"status": "revoked"},
    )
    assert revoked.status_code == 200

    eligibility = client.get(f"/contacts/{contact['id']}/eligibility", headers=auth_headers).json()
    assert eligibility["voice"]["allowed"] is False
    assert eligibility["voice"]["reason"] == "no_consent"


def test_suppression_blocks_contact_even_with_consent(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    contact = create_contact()
    client.put(
        f"/contacts/{contact['id']}/consents/voice",
        headers=auth_headers,
        json={"status": "granted"},
    )

    created = client.post(
        "/suppressions",
        headers=auth_headers,
        json={"channel": "voice", "value": "098765 00000", "reason": "dnd"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["value"] == contact["phone"]
    assert created.json()["reason"] == "dnd"

    eligibility = client.get(f"/contacts/{contact['id']}/eligibility", headers=auth_headers).json()
    assert eligibility["voice"]["allowed"] is False
    assert eligibility["voice"]["reason"] == "suppressed_dnd"

    duplicate = client.post(
        "/suppressions",
        headers=auth_headers,
        json={"channel": "voice", "value": contact["phone"]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_suppression"

    listing = client.get("/suppressions?search=dnd", headers=auth_headers).json()
    assert listing["total"] == 1

    suppression_id = created.json()["id"]
    assert client.delete(f"/suppressions/{suppression_id}", headers=auth_headers).status_code == 204

    restored = client.get(f"/contacts/{contact['id']}/eligibility", headers=auth_headers).json()
    assert restored["voice"]["allowed"] is True


def test_suppression_normalizes_email_and_rejects_invalid_values(
    client: TestClient, auth_headers: dict
) -> None:
    created = client.post(
        "/suppressions",
        headers=auth_headers,
        json={"channel": "email", "value": "  OptOut@Example.COM "},
    )
    assert created.status_code == 201
    assert created.json()["value"] == "optout@example.com"

    bad_phone = client.post(
        "/suppressions",
        headers=auth_headers,
        json={"channel": "voice", "value": "12345"},
    )
    assert bad_phone.status_code == 422
    assert bad_phone.json()["error"]["code"] == "invalid_phone"

    bad_email = client.post(
        "/suppressions",
        headers=auth_headers,
        json={"channel": "email", "value": "not-an-email"},
    )
    assert bad_email.status_code == 422


def test_missing_contact_details_are_reported(client: TestClient, auth_headers: dict) -> None:
    phone_only = client.post(
        "/contacts",
        headers=auth_headers,
        json={"name": "Phone Only", "phone": "+919876500500"},
    ).json()
    eligibility = client.get(
        f"/contacts/{phone_only['id']}/eligibility", headers=auth_headers
    ).json()
    assert eligibility["email"]["allowed"] is False
    assert eligibility["email"]["reason"] == "missing_contact_details"

    email_only = client.post(
        "/contacts",
        headers=auth_headers,
        json={"name": "Email Only", "email": "email-only@example.com"},
    ).json()
    eligibility = client.get(
        f"/contacts/{email_only['id']}/eligibility", headers=auth_headers
    ).json()
    assert eligibility["voice"]["reason"] == "missing_contact_details"


def test_suppressions_are_isolated_between_workspaces(
    client: TestClient, auth_headers: dict, other_headers: dict
) -> None:
    created = client.post(
        "/suppressions",
        headers=auth_headers,
        json={"channel": "voice", "value": "+919876500600", "reason": "manual"},
    ).json()

    assert client.get("/suppressions", headers=other_headers).json()["total"] == 0
    assert client.delete(f"/suppressions/{created['id']}", headers=other_headers).status_code == 404

    # The same number can be suppressed independently in another workspace.
    other = client.post(
        "/suppressions",
        headers=other_headers,
        json={"channel": "voice", "value": "+919876500600", "reason": "manual"},
    )
    assert other.status_code == 201


def test_unknown_suppression_returns_404(client: TestClient, auth_headers: dict) -> None:
    assert client.delete(f"/suppressions/{uuid.uuid4()}", headers=auth_headers).status_code == 404

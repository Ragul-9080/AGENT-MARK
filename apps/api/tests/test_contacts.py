from __future__ import annotations

import uuid

from app.services.contacts import normalize_phone
from fastapi.testclient import TestClient


def test_create_contact_normalizes_values(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    contact = create_contact(
        name="  Asha Rao  ",
        phone="098765 00001",
        email="  ASHA@Example.COM ",
        tags=["Lead", "lead", "  priority  ", ""],
    )
    assert contact["name"] == "Asha Rao"
    assert contact["phone"] == "+919876500001"
    assert contact["email"] == "asha@example.com"
    assert contact["tags"] == ["Lead", "priority"]
    assert contact["source"] == "manual"

    fetched = client.get(f"/contacts/{contact['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == contact["id"]


def test_contact_requires_phone_or_email(client: TestClient, auth_headers: dict) -> None:
    response = client.post("/contacts", json={"name": "No Details"}, headers=auth_headers)
    assert response.status_code == 422

    blank_phone = client.post(
        "/contacts", json={"phone": "   ", "email": None}, headers=auth_headers
    )
    assert blank_phone.status_code == 422


def test_invalid_contact_values_are_rejected(client: TestClient, auth_headers: dict) -> None:
    bad_phone = client.post("/contacts", json={"phone": "12345"}, headers=auth_headers)
    assert bad_phone.status_code == 422
    assert bad_phone.json()["error"]["code"] == "invalid_phone"

    bad_email = client.post("/contacts", json={"email": "not-an-email"}, headers=auth_headers)
    assert bad_email.status_code == 422


def test_duplicate_contact_is_rejected_by_phone_or_email(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    first = create_contact()

    same_phone = client.post(
        "/contacts",
        json={"name": "Other", "phone": first["phone"]},
        headers=auth_headers,
    )
    assert same_phone.status_code == 409
    assert same_phone.json()["error"]["code"] == "duplicate_contact"

    same_email = client.post(
        "/contacts",
        json={"name": "Other", "email": first["email"].upper()},
        headers=auth_headers,
    )
    assert same_email.status_code == 409


def test_update_and_delete_contact(client: TestClient, auth_headers: dict, create_contact) -> None:
    contact = create_contact()

    updated = client.patch(
        f"/contacts/{contact['id']}",
        headers=auth_headers,
        json={
            "name": "Asha Sharma",
            "tags": ["customer", "priority"],
            "language": "hi-IN",
            "custom_fields": {"city": "Pune"},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Asha Sharma"
    assert updated.json()["custom_fields"] == {"city": "Pune"}

    cleared = client.patch(f"/contacts/{contact['id']}", headers=auth_headers, json={"phone": None})
    assert cleared.status_code == 200
    assert cleared.json()["phone"] is None

    still_has_contact = client.patch(
        f"/contacts/{contact['id']}",
        headers=auth_headers,
        json={"phone": None, "email": None},
    )
    assert still_has_contact.status_code == 422

    deleted = client.delete(f"/contacts/{contact['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/contacts/{contact['id']}", headers=auth_headers).status_code == 404


def test_update_rejects_collision_with_another_contact(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    first = create_contact()
    second = create_contact(name="Second", phone="+919876500002", email="second@example.com")

    response = client.patch(
        f"/contacts/{second['id']}",
        headers=auth_headers,
        json={"phone": first["phone"]},
    )
    assert response.status_code == 409


def test_list_filters_search_and_pagination(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    create_contact(name="Asha Rao", phone="+919876500010", email="asha@example.com")
    create_contact(
        name="Bilal Khan",
        phone="+919876500011",
        email="bilal@example.com",
        tags=["customer"],
        language="hi-IN",
        source="website",
    )
    create_contact(name="Chen Wei", phone="+919876500012", email="chen@example.com")

    all_contacts = client.get("/contacts", headers=auth_headers).json()
    assert all_contacts["total"] == 3

    searched = client.get("/contacts?search=bilal", headers=auth_headers).json()
    assert searched["total"] == 1
    assert searched["items"][0]["name"] == "Bilal Khan"

    by_tag = client.get("/contacts?tag=customer", headers=auth_headers).json()
    assert by_tag["total"] == 1

    by_language = client.get("/contacts?language=hi-IN", headers=auth_headers).json()
    assert by_language["total"] == 1

    by_source = client.get("/contacts?source=website", headers=auth_headers).json()
    assert by_source["total"] == 1

    page = client.get("/contacts?limit=2&offset=0", headers=auth_headers).json()
    assert len(page["items"]) == 2
    assert page["total"] == 3

    second_page = client.get("/contacts?limit=2&offset=2", headers=auth_headers).json()
    assert len(second_page["items"]) == 1

    invalid_page = client.get("/contacts?limit=500", headers=auth_headers)
    assert invalid_page.status_code == 422


def test_contact_events_include_created_event(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    contact = create_contact()

    events = client.get(f"/contacts/{contact['id']}/events", headers=auth_headers)
    assert events.status_code == 200
    body = events.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "contact.created"
    assert body["items"][0]["source_module"] == "system"

    filtered = client.get(f"/contacts/{contact['id']}/events?module=email", headers=auth_headers)
    assert filtered.json()["total"] == 0


def test_contacts_are_isolated_between_workspaces(
    client: TestClient, auth_headers: dict, other_headers: dict, create_contact
) -> None:
    contact = create_contact()

    assert client.get("/contacts", headers=other_headers).json()["total"] == 0
    assert client.get(f"/contacts/{contact['id']}", headers=other_headers).status_code == 404
    assert (
        client.patch(
            f"/contacts/{contact['id']}",
            headers=other_headers,
            json={"name": "Hijacked"},
        ).status_code
        == 404
    )
    assert client.delete(f"/contacts/{contact['id']}", headers=other_headers).status_code == 404
    assert client.get(f"/contacts/{contact['id']}/events", headers=other_headers).status_code == 404
    assert (
        client.get(f"/contacts/{contact['id']}/consents", headers=other_headers).status_code == 404
    )
    assert (
        client.get(f"/contacts/{contact['id']}/eligibility", headers=other_headers).status_code
        == 404
    )

    # The owning workspace still sees the contact.
    assert client.get(f"/contacts/{contact['id']}", headers=auth_headers).status_code == 200


def test_unknown_contact_returns_404(client: TestClient, auth_headers: dict) -> None:
    missing = uuid.uuid4()
    assert client.get(f"/contacts/{missing}", headers=auth_headers).status_code == 404
    assert (
        client.patch(f"/contacts/{missing}", headers=auth_headers, json={"name": "x"}).status_code
        == 404
    )


def test_normalize_phone_edge_cases() -> None:
    assert normalize_phone(None) is None
    assert normalize_phone("   ") is None
    assert normalize_phone("09876543210") == "+919876543210"

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.conftest import imports_file


def _rows(count: int, start: int = 0) -> list[dict[str, str]]:
    return [
        {
            "name": f"Contact {index}",
            "phone": f"+9198765{index:05d}",
            "email": f"contact{index}@example.com",
            "tags": "imported,lead",
        }
        for index in range(start, start + count)
    ]


def test_preview_does_not_create_contacts(client: TestClient, auth_headers: dict) -> None:
    filename, content = imports_file(_rows(100))
    response = client.post(
        "/contacts/import",
        headers=auth_headers,
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dry_run"] is True
    assert body["total_rows"] == 100
    assert body["valid_rows"] == 100
    assert body["created"] == 0
    assert len(body["preview"]) == 50
    assert body["truncated"] is True

    assert client.get("/contacts", headers=auth_headers).json()["total"] == 0


def test_commit_imports_one_hundred_contacts(client: TestClient, auth_headers: dict) -> None:
    filename, content = imports_file(_rows(100))
    response = client.post(
        "/contacts/import?dry_run=false",
        headers=auth_headers,
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dry_run"] is False
    assert body["created"] == 100
    assert body["duplicate_rows"] == 0
    assert body["invalid_rows"] == 0

    listing = client.get("/contacts?limit=200", headers=auth_headers).json()
    assert listing["total"] == 100
    assert len(listing["items"]) == 100
    contact = next(item for item in listing["items"] if item["email"] == "contact0@example.com")
    assert contact["phone"] == "+919876500000"
    assert contact["tags"] == ["imported", "lead"]
    assert contact["source"] == "csv_import"
    assert contact["language"] == "en-IN"


def test_import_reports_invalid_and_duplicate_rows(
    client: TestClient, auth_headers: dict, create_contact
) -> None:
    create_contact(phone="+919876500100", email="existing@example.com")

    rows = [
        {"name": "Fine", "phone": "+919876500101", "email": "fine@example.com"},
        {"name": "Bad phone", "phone": "12345", "email": "badphone@example.com"},
        {"name": "Bad email", "phone": "+919876500102", "email": "nope"},
        {"name": "No details", "phone": "", "email": ""},
        {
            "name": "Repeats file phone",
            "phone": "+919876500101",
            "email": "repeat@example.com",
        },
        {
            "name": "Already in database",
            "phone": "+919876500100",
            "email": "new@example.com",
        },
    ]
    filename, content = imports_file(rows)
    response = client.post(
        "/contacts/import?dry_run=false",
        headers=auth_headers,
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_rows"] == 6
    assert body["valid_rows"] == 1
    assert body["invalid_rows"] == 3
    assert body["duplicate_rows"] == 2
    assert body["created"] == 1
    codes = {error["code"] for error in body["errors"]}
    assert {"invalid_phone", "invalid_email", "missing_contact_details"} <= codes
    assert "duplicate_in_file" in codes
    assert "duplicate_contact" in codes

    # A repeat commit imports nothing because the first run already created the contact.
    again = client.post(
        "/contacts/import?dry_run=false",
        headers=auth_headers,
        files={"file": (filename, content, "text/csv")},
    )
    assert again.status_code == 200
    assert again.json()["created"] == 0


def test_import_keeps_unknown_columns_as_custom_fields(
    client: TestClient, auth_headers: dict
) -> None:
    filename, content = imports_file(
        [
            {
                "name": "Custom Fields",
                "phone": "+919876500200",
                "email": "custom@example.com",
                "company": "Acme",
                "city": "Mumbai",
            }
        ],
        headers=["name", "phone", "email", "company", "city"],
    )
    response = client.post(
        "/contacts/import?dry_run=false",
        headers=auth_headers,
        files={"file": (filename, content, "text/csv")},
    )
    assert response.status_code == 200, response.text

    listing = client.get("/contacts", headers=auth_headers).json()
    contact = listing["items"][0]
    assert contact["custom_fields"] == {"company": "Acme", "city": "Mumbai"}


def test_import_requires_a_phone_or_email_column(client: TestClient, auth_headers: dict) -> None:
    filename, content = imports_file(
        [{"name": "No Channels", "notes": "x"}], headers=["name", "notes"]
    )
    response = client.post(
        "/contacts/import", headers=auth_headers, files={"file": (filename, content, "text/csv")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_csv"


def test_import_rejects_empty_and_oversized_files(
    client: TestClient, auth_headers: dict, monkeypatch
) -> None:
    empty = client.post(
        "/contacts/import",
        headers=auth_headers,
        files={"file": ("contacts.csv", b"", "text/csv")},
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "empty_file"

    from app.core.config import settings

    monkeypatch.setattr(settings, "contact_import_max_bytes", 64)
    filename, content = imports_file(_rows(10))
    oversized = client.post(
        "/contacts/import", headers=auth_headers, files={"file": (filename, content, "text/csv")}
    )
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "import_too_large"


def test_import_row_limit_is_enforced(client: TestClient, auth_headers: dict, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "contact_import_max_rows", 3)
    filename, content = imports_file(_rows(4))
    response = client.post(
        "/contacts/import", headers=auth_headers, files={"file": (filename, content, "text/csv")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "import_too_large"


def test_import_skips_blank_rows(client: TestClient, auth_headers: dict) -> None:
    filename, content = imports_file(
        [
            {"name": "One", "phone": "+919876500300", "email": "one@example.com"},
            {"name": "", "phone": "", "email": ""},
            {"name": "Two", "phone": "+919876500301", "email": "two@example.com"},
        ]
    )
    response = client.post(
        "/contacts/import", headers=auth_headers, files={"file": (filename, content, "text/csv")}
    )
    assert response.status_code == 200
    assert response.json()["total_rows"] == 2


def test_import_headers_are_case_insensitive(client: TestClient, auth_headers: dict) -> None:
    filename, content = imports_file(
        [{"name": "Upper", "phone": "+919876500400", "email": "upper@example.com"}],
        headers=["NAME", "Phone", "EMAIL"],
    )
    response = client.post(
        "/contacts/import?dry_run=false",
        headers=auth_headers,
        files={"file": (filename, content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 1

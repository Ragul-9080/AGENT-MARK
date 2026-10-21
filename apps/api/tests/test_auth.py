from __future__ import annotations

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth import normalize_email
from fastapi.testclient import TestClient
from sqlalchemy import select


def test_root_and_health(client: TestClient) -> None:
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["health"] == "/health"
    assert root.headers["X-Request-ID"]
    assert root.headers["X-Frame-Options"] == "DENY"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "up"


def test_register_returns_tokens_and_workspace(client: TestClient, account: dict) -> None:
    assert account["token_type"] == "bearer"
    assert account["access_token"] != account["refresh_token"]
    assert account["user"]["role"] == "owner"
    assert account["user"]["email"] == account["user"]["email"].lower()
    assert account["workspace"]["timezone"] == "Asia/Kolkata"
    assert account["workspace"]["settings"]["calling_hours"] == {
        "start": "09:00",
        "end": "21:00",
        "timezone": "contact",
    }


def test_duplicate_email_is_case_insensitive(client: TestClient, account: dict) -> None:
    response = client.post(
        "/auth/register",
        json={
            "workspace_name": "Another",
            "name": "Someone",
            "email": account["user"]["email"].upper(),
            "password": "another password",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_in_use"


def test_login_me_and_refresh(client: TestClient, account: dict) -> None:
    login = client.post(
        "/auth/login",
        json={"email": account["user"]["email"], "password": "correct horse battery"},
    )
    assert login.status_code == 200
    tokens = login.json()

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["id"] == account["user"]["id"]

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200

    wrong_password = client.post(
        "/auth/login",
        json={"email": account["user"]["email"], "password": "not the password"},
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


def test_token_cannot_be_used_for_the_wrong_purpose(client: TestClient, account: dict) -> None:
    refresh_as_access = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {account['refresh_token']}"}
    )
    assert refresh_as_access.status_code == 401

    access_as_refresh = client.post(
        "/auth/refresh", json={"refresh_token": account["access_token"]}
    )
    assert access_as_refresh.status_code == 401


def test_missing_and_malformed_tokens_are_rejected(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    bad = client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_token"


def test_inactive_user_cannot_sign_in(client: TestClient, account: dict, db) -> None:
    user = db.scalar(select(User).where(User.email == account["user"]["email"]))
    assert user is not None
    user.is_active = False
    db.commit()

    response = client.post(
        "/auth/login",
        json={"email": account["user"]["email"], "password": "correct horse battery"},
    )
    assert response.status_code == 401

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {account['access_token']}"})
    assert me.status_code == 401


def test_refresh_rejects_removed_user(client: TestClient, account: dict, db) -> None:
    user = db.scalar(select(User).where(User.email == account["user"]["email"]))
    assert user is not None
    db.delete(user)
    db.commit()

    response = client.post("/auth/refresh", json={"refresh_token": account["refresh_token"]})
    assert response.status_code == 401


def test_workspace_settings_and_member_permissions(
    client: TestClient, account: dict, auth_headers: dict, db
) -> None:
    update = client.patch(
        "/workspace",
        headers=auth_headers,
        json={
            "name": "Renamed Workspace",
            "timezone": "Asia/Dubai",
            "default_language": "hi-IN",
            "settings": {"calling_hours": "10:30-19:45", "recording_enabled": True},
        },
    )
    assert update.status_code == 200, update.text
    body = update.json()
    assert body["name"] == "Renamed Workspace"
    assert body["settings"]["calling_hours"] == {
        "start": "10:30",
        "end": "19:45",
        "timezone": "contact",
    }

    bad_timezone = client.patch(
        "/workspace", headers=auth_headers, json={"timezone": "Mars/Olympus"}
    )
    assert bad_timezone.status_code == 422

    bad_window = client.patch(
        "/workspace", headers=auth_headers, json={"settings": {"calling_hours": "20:00-08:00"}}
    )
    assert bad_window.status_code == 422
    assert bad_window.json()["error"]["code"] == "invalid_calling_window"

    member = User(
        workspace_id=account["workspace"]["id"],
        email="member@example.com",
        name="Member",
        password_hash=hash_password("member password"),
        role=UserRole.member,
    )
    db.add(member)
    db.commit()

    login = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member password"}
    )
    assert login.status_code == 200
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/workspace", headers=member_headers).status_code == 403
    assert client.get("/workspace/members", headers=member_headers).status_code == 403

    members = client.get("/workspace/members", headers=auth_headers)
    assert members.status_code == 200
    assert {item["email"] for item in members.json()} == {
        account["user"]["email"],
        "member@example.com",
    }


def test_validation_errors_have_stable_shape(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"workspace_name": "", "name": "", "email": "nope", "password": "short"},
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["request_id"]
    assert {"workspace_name", "email"} <= {item["field"] for item in body["details"]}


def test_normalize_email() -> None:
    assert normalize_email("  Owner@Example.COM ") == "owner@example.com"

from __future__ import annotations

import csv
import io
import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any

# The settings object is created at import time, so the test environment must be set
# before any application module is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/ama_test"
)
os.environ["JWT_SECRET"] = "test-secret-key-with-at-least-32-bytes"
os.environ["REDIS_URL"] = ""
os.environ["APP_ENV"] = "test"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "false"

import pytest  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.rate_limit import reset_rate_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Create a clean schema for the whole test session."""

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    """Truncate every table between tests and reset the rate limiter."""

    reset_rate_limiter()
    yield

    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))

    reset_rate_limiter()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


AccountFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def register_account(client: TestClient) -> AccountFactory:
    def _register(
        *,
        email: str | None = None,
        password: str = "correct horse battery",
        name: str = "Test Owner",
        workspace_name: str = "Test Workspace",
    ) -> dict[str, Any]:
        email = email or f"owner-{uuid.uuid4().hex[:10]}@example.com"
        response = client.post(
            "/auth/register",
            json={
                "workspace_name": workspace_name,
                "name": name,
                "email": email,
                "password": password,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _register


@pytest.fixture
def account(register_account: AccountFactory) -> dict[str, Any]:
    return register_account()


@pytest.fixture
def auth_headers(account: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {account['access_token']}"}


@pytest.fixture
def other_account(register_account: AccountFactory) -> dict[str, Any]:
    return register_account(email="other-owner@example.com", workspace_name="Other Workspace")


@pytest.fixture
def other_headers(other_account: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {other_account['access_token']}"}


ContactFactory = Callable[..., dict[str, Any]]


@pytest.fixture
def create_contact(client: TestClient, auth_headers: dict[str, str]) -> ContactFactory:
    def _create(**overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "Asha Rao",
            "phone": "+919876500000",
            "email": "asha@example.com",
            "language": "en-IN",
            "tags": ["lead"],
        }
        payload.update(overrides)
        response = client.post("/contacts", json=payload, headers=auth_headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


def imports_file(
    rows: list[dict[str, str]], *, headers: list[str] | None = None
) -> tuple[str, bytes]:
    """Build a CSV upload tuple without depending on pandas/csv helpers in tests."""

    fieldnames = headers or ["name", "phone", "email", "tags"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(fieldnames)
    for row in rows:
        lookup = {key.lower(): value for key, value in row.items()}
        writer.writerow([str(lookup.get(field.lower(), "")) for field in fieldnames])
    return "contacts.csv", buffer.getvalue().encode("utf-8")

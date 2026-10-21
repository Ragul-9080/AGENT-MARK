from __future__ import annotations

import uuid

import pytest
from app.core.errors import AppError
from app.core.pagination import validate_calling_window
from app.core.security import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import JobStatus
from app.schemas.campaign import CampaignCreate
from app.services import jobs as job_service
from app.services.campaigns import create_campaign, fail_campaign
from app.services.contacts import normalize_tags
from app.services.webhooks import verify_workspace_token, workspace_webhook_token


def test_calling_window_validation() -> None:
    assert validate_calling_window("09:00-21:00") == ("09:00", "21:00")
    assert validate_calling_window("9:5-18:7") == ("09:05", "18:07")

    for value in ("bad", "09:00", "25:00-26:00", "21:00-09:00", "09:00-09:00"):
        with pytest.raises(AppError) as excinfo:
            validate_calling_window(value)
        assert excinfo.value.status_code == 422


def test_password_hashing_and_tokens() -> None:
    hashed = hash_password("a strong password")
    assert hashed != "a strong password"
    assert verify_password("a strong password", hashed) is True
    assert verify_password("wrong", hashed) is False
    assert verify_password("wrong", "not-a-hash") is False

    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    tokens = create_token_pair(user_id, workspace_id, "owner")

    access = decode_token(tokens["access_token"], "access")
    assert access["sub"] == str(user_id)
    assert access["ws"] == str(workspace_id)
    assert access["role"] == "owner"

    with pytest.raises(AppError) as excinfo:
        decode_token(tokens["access_token"], "refresh")
    assert excinfo.value.status_code == 401

    with pytest.raises(AppError):
        decode_token("garbage", "access")


def test_webhook_workspace_tokens() -> None:
    workspace_id = uuid.uuid4()
    token = workspace_webhook_token(workspace_id)
    assert token == workspace_webhook_token(workspace_id)
    verify_workspace_token(workspace_id, token)

    with pytest.raises(AppError) as excinfo:
        verify_workspace_token(workspace_id, "wrong")
    assert excinfo.value.status_code == 401

    with pytest.raises(AppError):
        verify_workspace_token(uuid.uuid4(), token)


def test_tag_normalization() -> None:
    assert normalize_tags(None) == []
    assert normalize_tags(["  Lead ", "lead", "", "vip", "vip"]) == ["Lead", "vip"]
    assert len(normalize_tags([f"tag-{index}" for index in range(100)])) == 50


def test_job_lifecycle_helpers(db, account: dict) -> None:
    job = job_service.create_job(
        db,
        workspace_id=uuid.UUID(account["workspace"]["id"]),
        type="unit.test",
        payload={"a": 1},
    )
    db.commit()

    job_service.mark_running(db, job, 10)
    assert job.status == JobStatus.running
    assert job.attempts == 1
    assert job.started_at is not None

    job_service.mark_succeeded(db, job, {"ok": True})
    assert job.status == JobStatus.succeeded
    assert job.progress == 100
    assert job.result == {"ok": True}
    assert job.error is None

    job_service.mark_failed(db, job, "x" * 3000)
    assert job.status == JobStatus.failed
    assert len(job.error or "") == 2000

    job_service.mark_dead_letter(db, job, "gave up")
    assert job.status == JobStatus.dead_letter
    assert job.finished_at is not None
    db.commit()


def test_fail_campaign_records_reason(db, account: dict) -> None:
    campaign = create_campaign(
        db,
        workspace_id=uuid.UUID(account["workspace"]["id"]),
        data=CampaignCreate(type="email", name="Broken"),
    )
    fail_campaign(db, campaign=campaign, reason="provider rejected sender")
    db.commit()
    assert campaign.status.value == "failed"
    assert campaign.id is not None

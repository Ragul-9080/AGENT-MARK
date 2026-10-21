"""End-to-end smoke test for the Phase 1 platform (Milestone 1 acceptance).

It drives the running stack through the dashboard's own BFF proxy, exactly the way a
browser does, so it covers the API, the auth cookies, the proxy and the rendered pages.

Start both services first, then run:

    # terminal 1
    cd apps/api && uvicorn app.main:app --port 8000
    # terminal 2
    cd apps/web && API_INTERNAL_URL=http://127.0.0.1:8000 npm run dev
    # terminal 3 (repo root)
    .venv/Scripts/python scripts/smoke_test.py

Options let it point at other ports, e.g. when 8000 is busy:

    python scripts/smoke_test.py --web http://127.0.0.1:3000 --api http://127.0.0.1:8000

Exit code 0 means every check passed. Nothing here contacts a real provider: no calls
are placed and no email is sent, because Milestones 2-4 own that work.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
import uuid
from typing import Any

import httpx

CONTACT_COUNT = 100


class SmokeFailure(RuntimeError):
    pass


def step(label: str) -> None:
    print(f"\n=== {label} ===")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def build_csv(count: int = CONTACT_COUNT) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["name", "phone", "email", "language", "tags", "source"])
    for index in range(1, count + 1):
        writer.writerow(
            [
                f"Smoke Contact {index}",
                f"+9198{index:08d}",
                f"smoke{index}@example.com",
                "en",
                "renewal, high-intent" if index % 3 == 0 else "renewal",
                "smoke_test",
            ]
        )
    return buffer.getvalue().encode("utf-8")


def wait_for_api(api: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{api}/health", timeout=3)
            if response.status_code == 200:
                print(f"API healthy: {response.json()}")
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise SmokeFailure(f"The API at {api} never became healthy.")


def register(client: httpx.Client, web: str, tag: str) -> dict[str, Any]:
    response = client.post(
        f"{web}/api/auth/register",
        json={
            "workspace_name": f"Smoke Workspace {tag}",
            "name": "Smoke Owner",
            "email": f"smoke.owner.{tag}@example.com",
            "password": "smoke-password-123",
        },
    )
    check(response.status_code == 201, f"register failed: {response.status_code} {response.text}")
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web", default="http://127.0.0.1:3000", help="dashboard base URL")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()

    web = args.web.rstrip("/")
    api = args.api.rstrip("/")
    tag = uuid.uuid4().hex[:8]

    step("wait for the API")
    wait_for_api(api)

    with httpx.Client(timeout=30, follow_redirects=False) as client:
        step("register a workspace through the dashboard BFF")
        auth = register(client, web, tag)
        print(f"user={auth['user']['id']} workspace={auth['workspace']['id']} role={auth['user']['role']}")
        check(auth["user"]["role"] == "owner", "the first user is not an owner")

        step("auth/me through the BFF")
        me = client.get(f"{web}/api/backend/auth/me")
        check(me.status_code == 200, f"auth/me failed: {me.status_code}")
        check(me.json()["user"]["email"] == f"smoke.owner.{tag}@example.com", "auth/me returned another user")

        step(f"import {CONTACT_COUNT} contacts")
        files = {"file": ("contacts.csv", build_csv(), "text/csv")}
        preview = client.post(f"{web}/api/backend/contacts/import", params={"dry_run": "true"}, files=files)
        check(preview.status_code == 200, f"preview failed: {preview.status_code} {preview.text}")
        preview_body = preview.json()
        check(preview_body["valid_rows"] == CONTACT_COUNT, f"expected {CONTACT_COUNT} valid rows")
        check(preview_body["created"] == 0, "the dry run created contacts")
        print(f"dry run: total={preview_body['total_rows']} valid={preview_body['valid_rows']} created={preview_body['created']}")

        files = {"file": ("contacts.csv", build_csv(), "text/csv")}
        commit = client.post(f"{web}/api/backend/contacts/import", params={"dry_run": "false"}, files=files)
        check(commit.status_code == 200, f"import failed: {commit.status_code} {commit.text}")
        check(commit.json()["created"] == CONTACT_COUNT, "the import did not create every valid row")
        print(f"imported {commit.json()['created']} contacts")

        files = {"file": ("contacts.csv", build_csv(), "text/csv")}
        again = client.post(f"{web}/api/backend/contacts/import", params={"dry_run": "false"}, files=files)
        check(again.json()["created"] == 0, "a repeated import created duplicate contacts")
        print(f"re-import: created=0 duplicate={again.json()['duplicate_rows']}")

        step("see the imported contacts")
        listing = client.get(f"{web}/api/backend/contacts", params={"limit": 200})
        check(listing.status_code == 200, "listing contacts failed")
        contacts = listing.json()
        check(contacts["total"] == CONTACT_COUNT, f"expected {CONTACT_COUNT} contacts, saw {contacts['total']}")
        first = contacts["items"][0]
        print(f"total={contacts['total']} sample={first['name']} {first['phone']}")

        search = client.get(f"{web}/api/backend/contacts", params={"search": "Smoke Contact 99", "limit": 5})
        check(search.json()["total"] == 1, "search did not find exactly one contact")

        step("consent gate, then the suppression override")
        consent = client.put(
            f"{web}/api/backend/contacts/{first['id']}/consents/voice",
            json={"status": "granted", "proof": "https://example.com/consent/form-42"},
        )
        check(consent.status_code == 200, f"recording consent failed: {consent.text}")
        eligibility = client.get(f"{web}/api/backend/contacts/{first['id']}/eligibility").json()
        check(eligibility["voice"]["allowed"], "voice consent did not make the contact eligible")
        check(not eligibility["email"]["allowed"], "email should still be blocked without consent")
        print(f"voice allowed after consent, email blocked: {eligibility['email']['message']}")

        suppression = client.post(
            f"{web}/api/backend/suppressions",
            json={"channel": "voice", "value": first["phone"], "reason": "dnd"},
        )
        check(suppression.status_code == 201, f"adding a suppression failed: {suppression.text}")
        eligibility = client.get(f"{web}/api/backend/contacts/{first['id']}/eligibility").json()
        check(not eligibility["voice"]["allowed"], "the suppression did not override consent")
        check(eligibility["voice"]["reason"] == "suppressed_dnd", "unexpected eligibility reason")
        print(f"voice blocked after suppression: {eligibility['voice']['reason']}")

        step("campaign lifecycle")
        campaign = client.post(
            f"{web}/api/backend/campaigns",
            json={"type": "voice", "name": "Smoke voice campaign", "settings": {"objective": "Confirm renewal date"}},
        )
        check(campaign.status_code == 201, f"creating a campaign failed: {campaign.text}")
        campaign_body = campaign.json()
        check(campaign_body["status"] == "draft", "a new campaign is not a draft")
        campaign_id = campaign_body["id"]
        print(f"campaign {campaign_id} created as draft")

        recipient_ids = [item["id"] for item in contacts["items"][:30]]
        added = client.post(
            f"{web}/api/backend/campaigns/{campaign_id}/contacts", json={"contact_ids": recipient_ids}
        ).json()
        check(added["added"] == 30, f"expected 30 recipients, got {added}")
        print(f"recipients added={added['added']} skipped={added['skipped']}")

        added_again = client.post(
            f"{web}/api/backend/campaigns/{campaign_id}/contacts", json={"contact_ids": recipient_ids}
        ).json()
        check(added_again["added"] == 0, "duplicate recipients were added")

        for action, expected in (
            ("start", "running"),
            ("pause", "paused"),
            ("resume", "running"),
            ("stop", "completed"),
        ):
            response = client.post(f"{web}/api/backend/campaigns/{campaign_id}/{action}")
            check(response.status_code == 200, f"{action} failed: {response.status_code} {response.text}")
            check(response.json()["status"] == expected, f"{action} produced {response.json()['status']}")
            print(f"{action} -> {response.json()['status']}")

        illegal = client.post(f"{web}/api/backend/campaigns/{campaign_id}/pause")
        check(illegal.status_code == 409, f"an illegal transition returned {illegal.status_code}")
        print("pause after stop -> 409 as expected")

        step("dashboard summary")
        summary = client.get(f"{web}/api/backend/dashboard/summary").json()
        check(summary["contacts"] == CONTACT_COUNT, "the dashboard summary does not match the contact count")
        print(
            f"contacts={summary['contacts']} calls={summary['calls']} emails={summary['emails_sent']} "
            f"running={summary['running_campaigns']} events={len(summary['recent_events'])}"
        )

        step("render every dashboard page")
        pages = [
            "/",
            "/contacts",
            "/contacts/import",
            f"/contacts/{first['id']}",
            "/campaigns",
            f"/campaigns/{campaign_id}",
            "/settings",
            "/voice",
            "/seo",
            "/email",
        ]
        bodies: dict[str, str] = {}
        for page in pages:
            response = client.get(f"{web}{page}")
            check(response.status_code == 200, f"{page} returned {response.status_code}")
            bodies[page] = response.text
            print(f"{page} -> 200 ({len(response.text)} bytes)")

        check("Smoke Contact 1" in bodies["/contacts"], "the contacts page did not list the imported contacts")
        check("Granted" in bodies[f"/contacts/{first['id']}"], "the contact page did not show consent state")
        check("Smoke voice campaign" in bodies[f"/campaigns/{campaign_id}"], "the campaign page did not render")
        check("Suppression list" in bodies["/settings"], "the settings page did not render the suppression list")
        print("page content checks passed")

        step("error handling")
        bad_login = httpx.post(
            f"{web}/api/auth/login",
            json={"email": f"smoke.owner.{tag}@example.com", "password": "definitely-wrong"},
        )
        check(bad_login.status_code == 401, f"a bad password returned {bad_login.status_code}")
        missing = client.get(f"{web}/contacts/{uuid.UUID(int=0)}")
        check(missing.status_code == 404, f"a missing contact returned {missing.status_code}")
        anonymous = httpx.get(f"{web}/api/backend/contacts")
        check(anonymous.status_code == 401, f"an anonymous proxy call returned {anonymous.status_code}")
        print("bad login 401, missing contact 404, anonymous proxy call 401")

        step("workspace isolation")
        with httpx.Client(base_url=web, timeout=30, follow_redirects=False) as other:
            register(other, web, f"other{tag}")
            other_contacts = other.get("/api/backend/contacts", params={"limit": 200}).json()
            check(other_contacts["total"] == 0, "a second workspace saw the first workspace's contacts")
            cross = other.get(f"/api/backend/contacts/{first['id']}")
            check(cross.status_code == 404, f"a cross-workspace contact read returned {cross.status_code}")
            cross_campaign = other.get(f"/api/backend/campaigns/{campaign_id}")
            check(
                cross_campaign.status_code == 404,
                f"a cross-workspace campaign read returned {cross_campaign.status_code}",
            )
            print("other workspace: 0 contacts, cross-workspace reads 404")

    print("\nSMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as failure:
        print(f"\nSMOKE TEST FAILED: {failure}", file=sys.stderr)
        raise SystemExit(1) from failure

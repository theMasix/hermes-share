"""API integration tests for hermes-share."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hermes_share.config import settings
from hermes_share.main import app

from .test_hermes_reader import create_mock_hermes_db


@pytest.fixture
def test_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        hermes_db = Path(tmpdir) / "state.db"
        share_db = Path(tmpdir) / "share.db"
        create_mock_hermes_db(hermes_db)

        # Override settings for tests
        settings.hermes_db_path = hermes_db
        settings.share_db_path = share_db
        settings.management_api_key = "test-secret-key"
        settings.base_url = "http://testserver"

        client = TestClient(app)
        yield client


def test_healthz(test_env):
    response = test_env.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "noindex" in response.headers["x-robots-tag"]


def test_create_share_unauthorized(test_env):
    response = test_env.post("/api/v1/shares", json={"session_id": "sess_123"})
    assert response.status_code == 401


def test_create_and_fetch_share(test_env):
    # 1. Create share with API key
    headers = {"X-API-Key": "test-secret-key"}
    response = test_env.post(
        "/api/v1/shares",
        headers=headers,
        json={"session_id": "sess_123", "show_reasoning": True, "allow_live": True},
    )
    assert response.status_code == 201
    data = response.json()
    token = data["token"]
    assert token.startswith("sh_")
    assert data["url"] == f"http://testserver/s/{token}"

    # 2. Fetch public share snapshot (no auth required)
    fetch_resp = test_env.get(f"/api/v1/shares/{token}")
    assert fetch_resp.status_code == 200
    fetch_data = fetch_resp.json()
    assert fetch_data["session"]["id"] == "sess_123"
    assert len(fetch_data["messages"]) == 2
    # Verify redaction is applied
    assert "[REDACTED_GITHUB_TOKEN]" in fetch_data["messages"][0]["content"]

    # 3. View public HTML page
    html_resp = test_env.get(f"/s/{token}")
    assert html_resp.status_code == 200
    assert "noindex" in html_resp.headers["x-robots-tag"]
    assert "<title>" in html_resp.text

    # 4. Revoke share
    revoke_resp = test_env.delete(f"/api/v1/shares/{token}", headers=headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    # 5. Fetch after revoke should return 410 Gone
    after_revoke = test_env.get(f"/api/v1/shares/{token}")
    assert after_revoke.status_code == 410

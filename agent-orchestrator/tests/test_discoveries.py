import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2] / "agent-orchestrator"
sys.path.append(str(ROOT))

import main  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from users import InMemoryUserRepository  # type: ignore  # noqa: E402
from connections import InMemoryConnectionRepository  # type: ignore  # noqa: E402
from discoveries import InMemoryDiscoveryRepository  # type: ignore  # noqa: E402
from auth.dependencies import set_repo_provider  # type: ignore  # noqa: E402


def fresh_client() -> TestClient:
    repo = InMemoryUserRepository()
    main.repo_provider = repo
    main.connection_repo = InMemoryConnectionRepository()
    main.discovery_repo = InMemoryDiscoveryRepository()
    main.settings.mcp_stub_mode = True
    main.settings.mcp_base_url = ""
    set_repo_provider(repo)
    return TestClient(app)


def seed_user_and_connection(client: TestClient):
    reg = client.post(
        "/auth/register-email",
        json={
            "name": "Disc User",
            "email": "disc@example.com",
            "phone": "123456789",
            "designation": "Engineer",
            "company_address": "",
            "password": "password123",
            "confirm_password": "password123",
            "consent": True,
        },
    )
    assert reg.status_code == 200
    conn = client.post(
        "/connections",
        json={
            "tenant_id": "tenant-123",
            "subscription_ids": ["sub-1"],
            "provider": "oauth_delegated",
            "access_token": "fake",
            "rbac_tier": "inventory",
        },
    )
    assert conn.status_code == 200
    return conn.json()["connection_id"]


def test_discovery_requires_connection_scope():
    client = fresh_client()
    connection_id = seed_user_and_connection(client)
    # Unauthorized subscription should fail
    bad = client.post(
        "/discoveries",
        json={"connection_id": connection_id, "tenant_id": "tenant-123", "subscription_id": "sub-2", "tier": "inventory"},
    )
    assert bad.status_code == 400
    # Authorized subscription succeeds
    good = client.post(
        "/discoveries",
        json={"connection_id": connection_id, "tenant_id": "tenant-123", "subscription_id": "sub-1", "tier": "inventory"},
    )
    assert good.status_code == 200
    body = good.json()
    assert body["connection_id"] == connection_id
    assert body["tier"] == "inventory"
    assert body["stage"] == "persist"
    assert body["status"] == "completed"
    assert "results" in body


def test_chat_endpoint_runs_discovery_and_returns_plan():
    client = fresh_client()
    connection_id = seed_user_and_connection(client)
    resp = client.post(
        "/chat",
        json={
            "message": "Run inventory",
            "connection_id": connection_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-1",
            "tier": "inventory",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["discovery"]["connection_id"] == connection_id
    assert data["discovery"]["stage"] == "persist"
    assert len(data["plan"]) == 4
    assert data["plan"][0]["name"] == "validate"
    assert data["plan"][-1]["status"] == "completed"


def test_rbac_blocks_higher_tier():
    client = fresh_client()
    connection_id = seed_user_and_connection(client)
    resp = client.post(
        "/chat",
        json={
            "message": "Run security",
            "connection_id": connection_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-1",
            "tier": "security",
        },
    )
    assert resp.status_code == 403

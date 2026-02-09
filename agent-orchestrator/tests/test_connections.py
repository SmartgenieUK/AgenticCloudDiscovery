import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2] / "agent-orchestrator"
sys.path.append(str(ROOT))

import main  # type: ignore  # noqa: E402
from main import app  # type: ignore  # noqa: E402
from users import InMemoryUserRepository  # type: ignore  # noqa: E402
from connections import InMemoryConnectionRepository  # type: ignore  # noqa: E402
from auth.dependencies import set_repo_provider  # type: ignore  # noqa: E402


def fresh_client() -> TestClient:
    repo = InMemoryUserRepository()
    main.repo_provider = repo
    main.connection_repo = InMemoryConnectionRepository()
    set_repo_provider(repo)
    return TestClient(app)


def register_and_login(client: TestClient):
    payload = {
        "name": "Conn User",
        "email": "conn@example.com",
        "phone": "123456789",
        "designation": "Engineer",
        "company_address": "",
        "password": "password123",
        "confirm_password": "password123",
        "consent": True,
    }
    resp = client.post("/auth/register-email", json=payload)
    assert resp.status_code == 200
    return resp


def test_create_and_list_connections():
    client = fresh_client()
    register_and_login(client)
    conn_payload = {
        "tenant_id": "tenant-123",
        "subscription_ids": ["sub-abc"],
        "provider": "oauth_delegated",
        "access_token": "fake-token",
        "expires_at": "2026-12-31T00:00:00Z",
    }
    create_resp = client.post("/connections", json=conn_payload)
    assert create_resp.status_code == 200
    body = create_resp.json()
    assert body["tenant_id"] == "tenant-123"
    assert body["subscription_ids"] == ["sub-abc"]
    assert "access_token" not in body

    list_resp = client.get("/connections")
    assert list_resp.status_code == 200
    connections = list_resp.json()
    assert len(connections) == 1
    assert connections[0]["provider"] == "oauth_delegated"

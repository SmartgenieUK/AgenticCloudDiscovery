import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2] / "agent-orchestrator"
sys.path.append(str(ROOT))

import main  # type: ignore  # noqa: E402
from main import InMemoryUserRepository, app  # type: ignore  # noqa: E402


def fresh_client() -> TestClient:
    main.repo_provider = InMemoryUserRepository()
    main.oauth_state_store = {}
    main.settings.google_client_id = "test-google-id"
    main.settings.google_client_secret = "test-google-secret"
    main.settings.microsoft_client_id = "test-ms-id"
    main.settings.microsoft_client_secret = "test-ms-secret"
    return TestClient(app)


def test_email_registration_validation():
    client = fresh_client()
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "123456789",
        "designation": "Engineer",
        "company_address": "",
        "password": "password123",
        "confirm_password": "mismatch",
        "consent": True,
    }
    response = client.post("/auth/register-email", json=payload)
    assert response.status_code == 422
    payload["confirm_password"] = payload["password"]
    payload["consent"] = False
    response = client.post("/auth/register-email", json=payload)
    assert response.status_code == 422


def test_email_login_success_and_failure():
    client = fresh_client()
    base_payload = {
        "name": "Login User",
        "email": "login@example.com",
        "phone": "123456789",
        "designation": "Engineer",
        "company_address": "",
        "password": "password123",
        "confirm_password": "password123",
        "consent": True,
    }
    register_resp = client.post("/auth/register-email", json=base_payload)
    assert register_resp.status_code == 200
    login_resp = client.post("/auth/login-email", json={"email": base_payload["email"], "password": base_payload["password"]})
    assert login_resp.status_code == 200
    bad_login = client.post("/auth/login-email", json={"email": base_payload["email"], "password": "wrong"})
    assert bad_login.status_code == 401


def test_complete_profile_updates_required_fields():
    client = fresh_client()
    email = f"{uuid.uuid4()}@example.com"
    register_payload = {
        "name": "Profile User",
        "email": email,
        "phone": "5551234",
        "designation": "Analyst",
        "company_address": "",
        "password": "password123",
        "confirm_password": "password123",
        "consent": True,
    }
    reg_resp = client.post("/auth/register-email", json=register_payload)
    assert reg_resp.status_code == 200
    complete_resp = client.post(
        "/auth/complete-profile",
        json={
            "name": "Profile Updated",
            "phone": "777888999",
            "designation": "Lead",
            "company_address": "123 Street",
        },
    )
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["name"] == "Profile Updated"
    assert body["phone"] == "777888999"
    assert body["designation"] == "Lead"


class FakeOAuthClient:
    def __init__(self, userinfo: dict):
        self.userinfo = userinfo

    def create_authorization_url(self, url: str, state: str = None, **kwargs):
        return f"{url}?state={state or 'state'}", state or "state"

    def fetch_token(self, token_url: str, code: str):
        return {"access_token": "fake"}

    def get(self, url: str):
        class R:
            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        return R(self.userinfo)


def test_oauth_google_flow_creates_user(monkeypatch):
    client = fresh_client()
    userinfo = {"sub": "google-subject", "email": "oauth@example.com", "name": "OAuth User"}

    def fake_client(provider: str):
        assert provider == "google"
        return FakeOAuthClient(userinfo)

    monkeypatch.setattr(main, "get_oauth_client", fake_client)
    start_resp = client.get("/auth/oauth/google/start")
    assert start_resp.status_code == 200
    state = start_resp.json()["state"]
    callback_resp = client.get(f"/auth/oauth/google/callback?state={state}&code=fake-code", allow_redirects=False)
    assert callback_resp.status_code in (302, 307)
    assert "complete-profile" in callback_resp.headers["location"]
    created = main.repo_provider.get_by_email("oauth@example.com")
    assert created is not None
    assert created["auth_provider"] == "google"

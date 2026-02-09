"""
Integration tests for orchestrator → MCP → discovery workflow.

Simpler, focused tests that match the actual implementation.
"""
import pytest
from fastapi.testclient import TestClient

import main
from main import app
from users import InMemoryUserRepository
from connections import InMemoryConnectionRepository
from discoveries import InMemoryDiscoveryRepository
from auth.dependencies import set_repo_provider


@pytest.fixture
def client():
    """Test client with in-memory repositories."""
    # Initialize in-memory repositories
    user_repo = InMemoryUserRepository()
    connection_repo = InMemoryConnectionRepository()
    discovery_repo = InMemoryDiscoveryRepository()

    # Set repository providers by directly assigning to main module
    main.repo_provider = user_repo
    main.connection_repo = connection_repo
    main.discovery_repo = discovery_repo
    main.settings.mcp_stub_mode = True  # Use stub mode for tests
    set_repo_provider(user_repo)

    return TestClient(app)


def seed_user_and_connection(client: TestClient, rbac_tier="inventory", email_suffix=""):
    """Helper to create user and connection."""
    # Register
    reg = client.post(
        "/auth/register-email",
        json={
            "name": "Test User",
            "email": f"test{email_suffix}@example.com",
            "phone": "1234567890",
            "designation": "Engineer",
            "company_address": "123 Test St",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "consent": True,
        },
    )
    assert reg.status_code == 200

    # Create connection
    conn = client.post(
        "/connections",
        json={
            "tenant_id": "tenant-123",
            "subscription_ids": ["sub-456"],
            "provider": "oauth_delegated",
            "access_token": "mock-token",
            "expires_at": "2026-12-31T23:59:59Z",
            "rbac_tier": rbac_tier,
        },
    )
    assert conn.status_code == 200
    return conn.json()["connection_id"]


class TestBasicEndpoints:
    """Test basic API endpoints."""

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_user_registration_and_login(self, client):
        """Test complete user registration and login flow."""
        # Register
        register_payload = {
            "name": "Integration Test",
            "email": "integration@test.com",
            "phone": "1234567890",
            "designation": "Tester",
            "company_address": "456 Test Ave",
            "password": "Password123!",
            "confirm_password": "Password123!",
            "consent": True,
        }
        register_response = client.post("/auth/register-email", json=register_payload)
        assert register_response.status_code == 200
        user_data = register_response.json()
        assert "user_id" in user_data

        # Login
        login_response = client.post(
            "/auth/login-email",
            json={"email": "integration@test.com", "password": "Password123!"},
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.cookies

    def test_connection_flow(self, client):
        """Test connection creation and listing."""
        connection_id = seed_user_and_connection(client, rbac_tier="cost", email_suffix="_conn")

        # List connections
        list_response = client.get("/connections")
        assert list_response.status_code == 200
        connections = list_response.json()
        assert len(connections) == 1
        assert connections[0]["connection_id"] == connection_id
        assert connections[0]["provider"] == "oauth_delegated"
        assert "access_token" not in connections[0]  # Verify tokens not exposed


class TestDiscoveryWorkflow:
    """Test discovery workflow execution."""

    def test_discovery_basic_flow(self, client):
        """Test basic discovery execution with stub MCP."""
        connection_id = seed_user_and_connection(client, email_suffix="_disc1")

        # Execute discovery
        discovery_response = client.post(
            "/discoveries",
            json={
                "connection_id": connection_id,
                "tenant_id": "tenant-123",
                "subscription_id": "sub-456",
                "tier": "inventory",
            },
        )

        assert discovery_response.status_code == 200
        data = discovery_response.json()

        # Validate discovery response structure
        assert "discovery_id" in data
        assert data["connection_id"] == connection_id
        assert data["tier"] == "inventory"
        assert data["status"] == "completed"
        assert data["stage"] == "persist"
        assert "results" in data

    def test_discovery_requires_valid_scope(self, client):
        """Test discovery validates connection scope."""
        connection_id = seed_user_and_connection(client, email_suffix="_disc2")

        # Try unauthorized subscription
        response = client.post(
            "/discoveries",
            json={
                "connection_id": connection_id,
                "tenant_id": "tenant-123",
                "subscription_id": "unauthorized-sub",
                "tier": "inventory",
            },
        )

        assert response.status_code == 400
        assert "not authorized" in response.json()["detail"].lower()

    def test_discovery_rbac_enforcement(self, client):
        """Test RBAC tier enforcement."""
        connection_id = seed_user_and_connection(client, rbac_tier="inventory", email_suffix="_disc3")

        # Try security discovery with inventory connection (should fail)
        response = client.post(
            "/discoveries",
            json={
                "connection_id": connection_id,
                "tenant_id": "tenant-123",
                "subscription_id": "sub-456",
                "tier": "security",
            },
        )

        assert response.status_code == 403
        assert "does not allow" in response.json()["detail"].lower()

    def test_discovery_missing_connection(self, client):
        """Test discovery fails with nonexistent connection."""
        _ = seed_user_and_connection(client, email_suffix="_disc4")  # Create user for auth

        response = client.post(
            "/discoveries",
            json={
                "connection_id": "nonexistent",
                "tenant_id": "tenant-123",
                "subscription_id": "sub-456",
                "tier": "inventory",
            },
        )

        # Should fail with either 400 or 404 (both valid for missing connection)
        assert response.status_code in [400, 404]
        error_msg = response.json()["detail"].lower()
        assert "invalid connection" in error_msg or "not found" in error_msg or "not authorized" in error_msg


class TestChatEndpoint:
    """Test chat endpoint integration."""

    def test_chat_runs_discovery(self, client):
        """Test chat endpoint triggers discovery."""
        connection_id = seed_user_and_connection(client, email_suffix="_chat")

        response = client.post(
            "/chat",
            json={
                "message": "Show me my Azure resources",
                "connection_id": connection_id,
                "tenant_id": "tenant-123",
                "subscription_id": "sub-456",
                "tier": "inventory",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check for response field (could be 'response' or 'final_response')
        assert "final_response" in data or "response" in data
        assert "discovery" in data
        assert "plan" in data

        # Validate discovery was executed
        discovery = data["discovery"]
        assert discovery["status"] == "completed"
        assert discovery["tier"] == "inventory"

        # Validate plan structure
        plan = data["plan"]
        assert len(plan) == 4
        assert plan[0]["name"] == "validate"
        assert plan[-1]["status"] == "completed"


class TestAuthenticationSecurity:
    """Test authentication and security."""

    def test_unauthenticated_access_blocked(self, client):
        """Test unauthenticated requests are blocked."""
        # Try to access connections without authentication
        response = client.get("/connections")
        assert response.status_code == 401

        # Try to create discovery without authentication
        response = client.post(
            "/discoveries",
            json={
                "connection_id": "test",
                "tenant_id": "test",
                "subscription_id": "test",
                "tier": "inventory",
            },
        )
        assert response.status_code == 401


class TestMCPTools:
    """Test MCP tools endpoint."""

    def test_mcp_tools_endpoint(self, client):
        """Test MCP tools endpoint returns tool list."""
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()

        # Should have tools defined
        assert len(data) > 0

        # Check inventory_discovery tool exists
        assert "inventory_discovery" in data
        tool = data["inventory_discovery"]
        assert "description" in tool
        assert "inputs" in tool
        assert "outputs" in tool


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=.", "--cov-report=term-missing"])

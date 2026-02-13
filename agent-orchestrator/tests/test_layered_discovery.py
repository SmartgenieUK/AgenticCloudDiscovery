"""Integration tests for the layered discovery workflow."""
import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main
from main import app
from users import InMemoryUserRepository
from connections import InMemoryConnectionRepository
from discoveries import InMemoryDiscoveryRepository
from auth.dependencies import set_repo_provider
from auth.utils import rate_limit_store


@pytest.fixture
def client():
    """Test client with in-memory repositories and stub mode."""
    rate_limit_store.clear()

    user_repo = InMemoryUserRepository()
    connection_repo = InMemoryConnectionRepository()
    discovery_repo = InMemoryDiscoveryRepository()

    main.repo_provider = user_repo
    main.connection_repo = connection_repo
    main.discovery_repo = discovery_repo
    main.settings.mcp_stub_mode = True
    set_repo_provider(user_repo)

    return TestClient(app)


def seed_user_and_connection(client: TestClient):
    """Helper to create user and connection, returns connection_id."""
    reg = client.post(
        "/auth/register-email",
        json={
            "name": "Test User",
            "email": "layertest@example.com",
            "phone": "1234567890",
            "designation": "Engineer",
            "company_address": "123 Test St",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "consent": True,
        },
    )
    assert reg.status_code == 200

    conn = client.post(
        "/connections",
        json={
            "tenant_id": "tenant-123",
            "subscription_ids": ["sub-456"],
            "provider": "oauth_delegated",
            "rbac_tier": "inventory",
        },
    )
    assert conn.status_code == 200
    return conn.json()["connection_id"]


# ====================== GET /layers ======================

class TestLayersEndpoint:
    def test_list_layers_returns_all_8(self, client):
        # Need auth for seeded user - but /layers doesn't need auth
        resp = client.get("/layers")
        assert resp.status_code == 200
        layers = resp.json()
        assert len(layers) == 8

    def test_layers_sorted_by_number(self, client):
        resp = client.get("/layers")
        layers = resp.json()
        numbers = [l["layer_number"] for l in layers]
        assert numbers == sorted(numbers)

    def test_first_3_enabled(self, client):
        resp = client.get("/layers")
        layers = resp.json()
        enabled = [l for l in layers if l["enabled"]]
        assert len(enabled) == 3
        assert [l["layer_id"] for l in enabled] == ["inventory", "topology", "identity_access"]

    def test_layer_has_expected_fields(self, client):
        resp = client.get("/layers")
        layer = resp.json()[0]
        assert "layer_id" in layer
        assert "layer_number" in layer
        assert "label" in layer
        assert "description" in layer
        assert "depends_on" in layer
        assert "enabled" in layer


# ====================== Chat with Layers ======================

class TestChatWithLayers:
    def test_inventory_only(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/chat", json={
            "message": "Run discovery",
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
            "layers": ["inventory"],
        })
        assert resp.status_code == 200
        data = resp.json()

        # Has layer_plan
        assert data["layer_plan"] is not None
        assert len(data["layer_plan"]) == 1
        assert data["layer_plan"][0]["layer_id"] == "inventory"
        assert data["layer_plan"][0]["status"] == "completed"
        assert data["layer_plan"][0]["auto_resolved"] is False

        # Has flat plan for backward compat
        assert len(data["plan"]) >= 3  # validate + inventory + aggregate + persist

        # Has backward-compat results
        disc = data["discovery"]
        assert disc["status"] == "completed"
        assert disc["results"]["inventory"] is not None
        assert disc["results"]["categories"] is not None
        assert disc["results"]["layers"]["inventory"] is not None

    def test_topology_auto_resolves_inventory(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/chat", json={
            "message": "Run discovery",
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
            "layers": ["topology"],
        })
        assert resp.status_code == 200
        data = resp.json()

        layer_plan = data["layer_plan"]
        assert len(layer_plan) == 2

        # Inventory auto-resolved
        inv_lp = layer_plan[0]
        assert inv_lp["layer_id"] == "inventory"
        assert inv_lp["auto_resolved"] is True
        assert inv_lp["status"] == "completed"

        # Topology was explicitly requested
        topo_lp = layer_plan[1]
        assert topo_lp["layer_id"] == "topology"
        assert topo_lp["auto_resolved"] is False
        assert topo_lp["status"] == "completed"

        # Topology should have 1 Resource Graph tool step
        assert len(topo_lp["steps"]) == 1  # rg_topology_discovery

    def test_all_three_layers(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/chat", json={
            "message": "Run discovery",
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
            "layers": ["inventory", "topology", "identity_access"],
        })
        assert resp.status_code == 200
        data = resp.json()

        layer_plan = data["layer_plan"]
        assert len(layer_plan) == 3
        assert [lp["layer_id"] for lp in layer_plan] == ["inventory", "topology", "identity_access"]

        # All completed
        for lp in layer_plan:
            assert lp["status"] == "completed"

        # Identity layer should have 2 Resource Graph tools
        ia_lp = layer_plan[2]
        assert len(ia_lp["steps"]) == 2

        # Summary mentions all 3 layers
        assert "3 layers" in data["final_response"]

    def test_without_layers_uses_old_workflow(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/chat", json={
            "message": "Run discovery",
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
        })
        assert resp.status_code == 200
        data = resp.json()

        # No layer_plan when using old workflow
        assert data.get("layer_plan") is None

        # Has flat plan with category steps
        plan_names = [s["name"] for s in data["plan"]]
        assert "validate" in plan_names
        assert "inventory" in plan_names
        assert "aggregate" in plan_names

    def test_layer_analysis_is_stub(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/chat", json={
            "message": "Run discovery",
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
            "layers": ["inventory"],
        })
        assert resp.status_code == 200
        data = resp.json()

        lp = data["layer_plan"][0]
        assert lp["analysis"]["status"] == "completed"
        assert lp["analysis"]["detail"]["mode"] == "stub"

        # Check analysis in results
        layer_result = data["discovery"]["results"]["layers"]["inventory"]
        assert layer_result["analysis"]["status"] == "stub"

    def test_tool_steps_have_resource_counts(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/chat", json={
            "message": "Run discovery",
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
            "layers": ["topology"],
        })
        assert resp.status_code == 200
        data = resp.json()

        topo_lp = data["layer_plan"][1]  # topology is second (after auto-resolved inventory)
        # At least some tool steps should have resources
        completed_steps = [s for s in topo_lp["steps"] if s["status"] == "completed"]
        assert len(completed_steps) > 0
        for step in completed_steps:
            assert "resource_count" in step.get("detail", {})


# ====================== POST /discoveries with Layers ======================

class TestDiscoveriesWithLayers:
    def test_discoveries_with_layers(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/discoveries", json={
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
            "layers": ["inventory"],
        })
        assert resp.status_code == 200
        disc = resp.json()
        assert disc["status"] == "completed"
        assert "layers" in disc["results"]

    def test_discoveries_without_layers_backward_compat(self, client):
        conn_id = seed_user_and_connection(client)
        resp = client.post("/discoveries", json={
            "connection_id": conn_id,
            "tenant_id": "tenant-123",
            "subscription_id": "sub-456",
        })
        assert resp.status_code == 200
        disc = resp.json()
        assert disc["status"] == "completed"
        # Old-style results
        assert "inventory" in disc["results"]
        assert "categories" in disc["results"]

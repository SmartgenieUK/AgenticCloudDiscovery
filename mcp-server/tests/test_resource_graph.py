"""Tests for Resource Graph tool definitions, execution, pagination, and throttle handling."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repositories import DEFAULT_TOOLS, InMemoryToolRepository, seed_default_tools
from executor import ToolExecutor
from models import ExecuteToolRequest


RG_TOOL_IDS = [
    "rg_inventory_discovery",
    "rg_topology_discovery",
    "rg_identity_discovery",
    "rg_policy_discovery",
]


@pytest.fixture
def seeded_repo():
    repo = InMemoryToolRepository()
    seed_default_tools(repo)
    return repo


# ====================== Tool Registry ======================

class TestRGToolDefinitions:
    def test_all_rg_tools_in_default_tools(self):
        tool_ids = [t["tool_id"] for t in DEFAULT_TOOLS]
        for tid in RG_TOOL_IDS:
            assert tid in tool_ids, f"{tid} missing from DEFAULT_TOOLS"

    def test_all_rg_tools_are_approved(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert tool is not None, f"{tid} not in repo"
            assert tool["status"] == "approved"

    def test_all_rg_tools_use_post(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert tool["allowed_methods"] == ["POST"], f"{tid} should use POST"

    def test_all_rg_tools_have_correct_endpoint(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert tool["endpoint"] == "/providers/Microsoft.ResourceGraph/resources"

    def test_all_rg_tools_have_kql_template(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert "kql_template" in tool
            assert len(tool["kql_template"]) > 10

    def test_rg_inventory_queries_resources_table(self, seeded_repo):
        tool = seeded_repo.get_by_id("rg_inventory_discovery")
        assert tool["kql_template"].startswith("resources |")

    def test_rg_topology_filters_network_types(self, seeded_repo):
        tool = seeded_repo.get_by_id("rg_topology_discovery")
        assert "microsoft.network/networkinterfaces" in tool["kql_template"].lower()
        assert "microsoft.network/loadbalancers" in tool["kql_template"].lower()

    def test_rg_identity_queries_authorizationresources(self, seeded_repo):
        tool = seeded_repo.get_by_id("rg_identity_discovery")
        assert tool["kql_template"].startswith("authorizationresources |")

    def test_rg_policy_queries_policyresources(self, seeded_repo):
        tool = seeded_repo.get_by_id("rg_policy_discovery")
        assert tool["kql_template"].startswith("policyresources |")

    def test_all_rg_tools_api_version(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert tool["api_version"] == "2022-10-01"

    def test_all_rg_tools_category_is_resource_graph(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert tool["category"] == "resource_graph"

    def test_all_rg_tools_require_subscription_ids(self, seeded_repo):
        for tid in RG_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert "subscription_ids" in tool["args_schema"]


# ====================== Normalizer ======================

class TestRGNormalizer:
    @pytest.fixture
    def executor(self):
        return ToolExecutor(apim_base_url=None, stub_mode=True, timeout=5.0)

    def test_inventory_normalizer(self, executor):
        resources = [
            {"type": "Microsoft.Compute/virtualMachines", "name": "vm1"},
            {"type": "Microsoft.Compute/virtualMachines", "name": "vm2"},
            {"type": "Microsoft.Storage/storageAccounts", "name": "sa1"},
        ]
        result = executor._normalize_rg_response("rg_inventory_discovery", resources, 3)
        assert result["counts"]["resources"] == 3
        assert result["counts"]["types"] == 2
        assert result["type_breakdown"]["Microsoft.Compute/virtualMachines"] == 2
        assert result["type_breakdown"]["Microsoft.Storage/storageAccounts"] == 1
        assert result["total_records"] == 3
        assert "Resource Graph" in result["summary"]

    def test_topology_normalizer(self, executor):
        resources = [
            {"type": "Microsoft.Network/networkInterfaces", "name": "nic1"},
            {"type": "Microsoft.Network/loadBalancers", "name": "lb1"},
        ]
        result = executor._normalize_rg_response("rg_topology_discovery", resources, 2)
        assert result["counts"]["resources"] == 2
        assert result["counts"]["types"] == 2
        assert "network resources" in result["summary"]

    def test_identity_normalizer(self, executor):
        resources = [
            {"type": "Microsoft.Authorization/roleAssignments", "name": "ra1"},
            {"type": "Microsoft.Authorization/roleAssignments", "name": "ra2"},
            {"type": "Microsoft.Authorization/roleDefinitions", "name": "rd1"},
        ]
        result = executor._normalize_rg_response("rg_identity_discovery", resources, 3)
        assert result["counts"]["role_assignments"] == 2
        assert result["counts"]["role_definitions"] == 1

    def test_policy_normalizer(self, executor):
        resources = [
            {"type": "Microsoft.Authorization/policyAssignments", "name": "pa1"},
        ]
        result = executor._normalize_rg_response("rg_policy_discovery", resources, 1)
        assert result["counts"]["policy_assignments"] == 1


# ====================== Throttle Header Parsing ======================

class TestThrottleHeaderParsing:
    def test_parse_remaining_and_resets(self):
        import httpx
        headers = httpx.Headers({
            "x-ms-user-quota-remaining": "3",
            "x-ms-user-quota-resets-after": "00:00:05",
        })
        remaining, resets = ToolExecutor._parse_throttle_headers(headers)
        assert remaining == 3
        assert resets == 5.0

    def test_parse_zero_remaining(self):
        import httpx
        headers = httpx.Headers({
            "x-ms-user-quota-remaining": "0",
            "x-ms-user-quota-resets-after": "00:00:10",
        })
        remaining, resets = ToolExecutor._parse_throttle_headers(headers)
        assert remaining == 0
        assert resets == 10.0

    def test_parse_missing_headers(self):
        import httpx
        headers = httpx.Headers({})
        remaining, resets = ToolExecutor._parse_throttle_headers(headers)
        assert remaining is None
        assert resets is None

    def test_parse_partial_headers(self):
        import httpx
        headers = httpx.Headers({"x-ms-user-quota-remaining": "5"})
        remaining, resets = ToolExecutor._parse_throttle_headers(headers)
        assert remaining == 5
        assert resets is None

    def test_parse_complex_time(self):
        import httpx
        headers = httpx.Headers({
            "x-ms-user-quota-remaining": "1",
            "x-ms-user-quota-resets-after": "00:01:30",
        })
        remaining, resets = ToolExecutor._parse_throttle_headers(headers)
        assert remaining == 1
        assert resets == 90.0

    def test_parse_invalid_remaining(self):
        import httpx
        headers = httpx.Headers({"x-ms-user-quota-remaining": "abc"})
        remaining, resets = ToolExecutor._parse_throttle_headers(headers)
        assert remaining is None


# ====================== Pagination Simulation ======================

class TestPaginationLoop:
    """Test the pagination loop logic by mocking httpx responses."""

    def test_single_page_no_skip_token(self, monkeypatch):
        executor = ToolExecutor(apim_base_url=None, stub_mode=False, timeout=5.0)
        tool = {
            "tool_id": "rg_inventory_discovery",
            "endpoint": "/providers/Microsoft.ResourceGraph/resources",
            "api_version": "2022-10-01",
            "kql_template": "resources | project id, name, type",
        }
        request = ExecuteToolRequest(
            session_id="sess-1", tool_id="rg_inventory_discovery",
            args={"subscription_ids": ["sub-1"]},
            connection_id="conn-1", agent_step=1, attempt=1,
        )

        class MockResponse:
            status_code = 200
            headers = {}
            def json(self):
                return {"data": [{"id": "r1"}, {"id": "r2"}], "totalRecords": 2}
            def raise_for_status(self):
                pass

        class MockClient:
            def __init__(self, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def post(self, url, headers=None, json=None):
                return MockResponse()

        monkeypatch.setattr("httpx.Client", MockClient)
        resources, total = executor._execute_resource_graph(
            request, tool, {"Authorization": "Bearer test"}, ["sub-1"]
        )
        assert len(resources) == 2
        assert total == 2

    def test_multi_page_with_skip_token(self, monkeypatch):
        executor = ToolExecutor(apim_base_url=None, stub_mode=False, timeout=5.0)
        tool = {
            "tool_id": "rg_inventory_discovery",
            "endpoint": "/providers/Microsoft.ResourceGraph/resources",
            "api_version": "2022-10-01",
            "kql_template": "resources | project id, name, type",
        }
        request = ExecuteToolRequest(
            session_id="sess-1", tool_id="rg_inventory_discovery",
            args={"subscription_ids": ["sub-1"]},
            connection_id="conn-1", agent_step=1, attempt=1,
        )

        call_count = {"n": 0}

        class MockResponse:
            def __init__(self, page):
                self.status_code = 200
                self.headers = {}
                self.page = page
            def json(self):
                if self.page == 1:
                    return {"data": [{"id": f"r{i}"} for i in range(1000)], "$skipToken": "token-page2", "totalRecords": 2500}
                elif self.page == 2:
                    return {"data": [{"id": f"r{i}"} for i in range(1000, 2000)], "$skipToken": "token-page3", "totalRecords": 2500}
                else:
                    return {"data": [{"id": f"r{i}"} for i in range(2000, 2500)], "totalRecords": 2500}
            def raise_for_status(self):
                pass

        class MockClient:
            def __init__(self, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def post(self, url, headers=None, json=None):
                call_count["n"] += 1
                return MockResponse(call_count["n"])

        monkeypatch.setattr("httpx.Client", MockClient)
        resources, total = executor._execute_resource_graph(
            request, tool, {"Authorization": "Bearer test"}, ["sub-1"]
        )
        assert len(resources) == 2500
        assert total == 2500
        assert call_count["n"] == 3

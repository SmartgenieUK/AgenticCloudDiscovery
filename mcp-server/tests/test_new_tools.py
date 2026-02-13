"""Tests for Layer 2 (Topology) and Layer 3 (Identity & Access) tool definitions."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from repositories import DEFAULT_TOOLS, InMemoryToolRepository, seed_default_tools
from executor import ToolExecutor
from models import ExecuteToolRequest


# ====================== Tool Registry ======================

TOPOLOGY_TOOL_IDS = [
    "nic_discovery",
    "nsg_discovery",
    "public_ip_discovery",
    "vnet_peering_discovery",
    "route_table_discovery",
    "private_endpoint_discovery",
    "load_balancer_discovery",
]

IDENTITY_TOOL_IDS = [
    "role_assignment_discovery",
    "role_definition_discovery",
    "policy_assignment_discovery",
]

ALL_NEW_TOOL_IDS = TOPOLOGY_TOOL_IDS + IDENTITY_TOOL_IDS


@pytest.fixture
def seeded_repo():
    repo = InMemoryToolRepository()
    seed_default_tools(repo)
    return repo


@pytest.fixture
def executor():
    return ToolExecutor(apim_base_url=None, stub_mode=False, timeout=5.0)


class TestToolDefinitions:
    def test_all_topology_tools_in_default_tools(self):
        tool_ids = [t["tool_id"] for t in DEFAULT_TOOLS]
        for tid in TOPOLOGY_TOOL_IDS:
            assert tid in tool_ids, f"{tid} missing from DEFAULT_TOOLS"

    def test_all_identity_tools_in_default_tools(self):
        tool_ids = [t["tool_id"] for t in DEFAULT_TOOLS]
        for tid in IDENTITY_TOOL_IDS:
            assert tid in tool_ids, f"{tid} missing from DEFAULT_TOOLS"

    def test_all_new_tools_are_approved(self):
        tool_map = {t["tool_id"]: t for t in DEFAULT_TOOLS}
        for tid in ALL_NEW_TOOL_IDS:
            assert tool_map[tid]["status"] == "approved"

    def test_all_new_tools_are_get_only(self):
        tool_map = {t["tool_id"]: t for t in DEFAULT_TOOLS}
        for tid in ALL_NEW_TOOL_IDS:
            assert tool_map[tid]["allowed_methods"] == ["GET"]

    def test_all_new_tools_target_arm(self):
        tool_map = {t["tool_id"]: t for t in DEFAULT_TOOLS}
        for tid in ALL_NEW_TOOL_IDS:
            assert "management.azure.com" in tool_map[tid]["allowed_domains"]

    def test_topology_tools_have_correct_category(self):
        tool_map = {t["tool_id"]: t for t in DEFAULT_TOOLS}
        for tid in TOPOLOGY_TOOL_IDS:
            assert tool_map[tid]["category"] == "topology"

    def test_identity_tools_have_correct_category(self):
        tool_map = {t["tool_id"]: t for t in DEFAULT_TOOLS}
        for tid in IDENTITY_TOOL_IDS:
            assert tool_map[tid]["category"] == "identity_access"

    def test_seeded_repo_has_new_tools(self, seeded_repo):
        for tid in ALL_NEW_TOOL_IDS:
            tool = seeded_repo.get_by_id(tid)
            assert tool is not None, f"{tid} not found in seeded repo"

    def test_total_tool_count(self):
        # 8 original + 10 new + 4 resource graph = 22
        assert len(DEFAULT_TOOLS) == 22


# ====================== Response Normalization ======================

class TestNormalization:
    @pytest.mark.parametrize("tool_id,resource_key,count_key", [
        ("nic_discovery", "nics", "nics"),
        ("nsg_discovery", "nsgs", "nsgs"),
        ("public_ip_discovery", "public_ips", "public_ips"),
        ("vnet_peering_discovery", "vnets_with_peerings", "vnets_with_peerings"),
        ("route_table_discovery", "route_tables", "route_tables"),
        ("private_endpoint_discovery", "private_endpoints", "private_endpoints"),
        ("load_balancer_discovery", "load_balancers", "load_balancers"),
        ("role_assignment_discovery", "role_assignments", "role_assignments"),
        ("role_definition_discovery", "role_definitions", "role_definitions"),
        ("policy_assignment_discovery", "policy_assignments", "policy_assignments"),
    ])
    def test_normalize_arm_response(self, executor, tool_id, resource_key, count_key):
        # Simulate ARM response format
        raw = {"value": [{"name": "item-1"}, {"name": "item-2"}]}
        result = executor._normalize_arm_response(tool_id, raw)
        assert "summary" in result
        assert "counts" in result
        assert count_key in result["counts"]
        assert result["counts"][count_key] == 2
        assert "timestamp" in result
        assert "resources" in result
        assert len(result["resources"]) == 2

"""Unit tests for the graph builder module."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph.graph_builder import (
    parse_resource_id,
    build_graph_from_discovery,
    _collect_resources_from_layers,
    _infer_topology_edges,
    _infer_identity_edges,
)


# ====================== parse_resource_id ======================

class TestParseResourceId:
    def test_full_resource_id(self):
        rid = "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web-01"
        parsed = parse_resource_id(rid)
        assert parsed["subscription_id"] == "sub-1"
        assert parsed["resource_group"] == "rg-prod"
        assert parsed["provider_namespace"] == "Microsoft.Compute"
        assert parsed["resource_type"] == "virtualMachines"
        assert parsed["name"] == "vm-web-01"

    def test_subscription_level_resource(self):
        rid = "/subscriptions/sub-1/providers/Microsoft.Authorization/roleAssignments/ra-001"
        parsed = parse_resource_id(rid)
        assert parsed["subscription_id"] == "sub-1"
        assert parsed["resource_group"] is None
        assert parsed["provider_namespace"] == "Microsoft.Authorization"
        assert parsed["resource_type"] == "roleAssignments"
        assert parsed["name"] == "ra-001"

    def test_subscription_only(self):
        rid = "/subscriptions/sub-1"
        parsed = parse_resource_id(rid)
        assert parsed["subscription_id"] == "sub-1"
        assert parsed["resource_group"] is None
        assert parsed["provider_namespace"] is None

    def test_resource_group_only(self):
        rid = "/subscriptions/sub-1/resourceGroups/rg-prod"
        parsed = parse_resource_id(rid)
        assert parsed["subscription_id"] == "sub-1"
        assert parsed["resource_group"] == "rg-prod"
        assert parsed["provider_namespace"] is None

    def test_invalid_id_returns_raw(self):
        parsed = parse_resource_id("not-an-azure-id")
        assert "raw" in parsed

    def test_case_insensitive(self):
        rid = "/Subscriptions/SUB-1/ResourceGroups/RG-PROD/providers/Microsoft.Compute/virtualMachines/vm-01"
        parsed = parse_resource_id(rid)
        assert parsed["subscription_id"] == "SUB-1"
        assert parsed["resource_group"] == "RG-PROD"


# ====================== Stub Discovery Data ======================

def _make_stub_discovery():
    """Build a realistic stub discovery document matching the layered workflow output."""
    return {
        "discovery_id": "disc-001",
        "connection_id": "conn-001",
        "tenant_id": "tenant-123",
        "subscription_id": "sub-1",
        "status": "completed",
        "stage": "persist",
        "results": {
            "layers": {
                "inventory": {
                    "tools": {
                        "rg_inventory_discovery": {
                            "status": "completed",
                            "resource_count": 10,
                            "resources": [
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web-01", "name": "vm-web-01", "type": "Microsoft.Compute/virtualMachines", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"vmSize": "Standard_D4s_v3"}, "tags": {}},
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-api-01", "name": "vm-api-01", "type": "Microsoft.Compute/virtualMachines", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"vmSize": "Standard_D2s_v3"}, "tags": {}},
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/stproddata01", "name": "stproddata01", "type": "Microsoft.Storage/storageAccounts", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {}, "tags": {}},
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-prod-01", "name": "sql-prod-01", "type": "Microsoft.Sql/servers", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {}, "tags": {}},
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod", "name": "vnet-prod", "type": "Microsoft.Network/virtualNetworks", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {}, "tags": {}},
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/networkSecurityGroups/nsg-web", "name": "nsg-web", "type": "Microsoft.Network/networkSecurityGroups", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {}, "tags": {}},
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Web/sites/app-frontend", "name": "app-frontend", "type": "Microsoft.Web/sites", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {}, "tags": {}},
                            ],
                        },
                    },
                },
                "topology": {
                    "tools": {
                        "rg_topology_discovery": {
                            "status": "completed",
                            "resource_count": 5,
                            "resources": [
                                # NIC with cross-references (vm, nsg, subnet)
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/networkInterfaces/nic-vm-web-01", "name": "nic-vm-web-01", "type": "Microsoft.Network/networkInterfaces", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"virtualMachine": {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web-01"}, "networkSecurityGroup": {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/networkSecurityGroups/nsg-web"}, "ipConfigurations": [{"name": "ipconfig1", "properties": {"subnet": {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-web"}}}]}, "tags": {}},
                                # Duplicate: vnet-prod (also in inventory — should be deduped)
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod", "name": "vnet-prod", "type": "Microsoft.Network/virtualNetworks", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}, "tags": {}},
                                # Duplicate: nsg-web (also in inventory)
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/networkSecurityGroups/nsg-web", "name": "nsg-web", "type": "Microsoft.Network/networkSecurityGroups", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"securityRules": [{"name": "Allow-HTTP"}]}, "tags": {}},
                                # PE with privateLinkServiceId
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/privateEndpoints/pe-sql-prod", "name": "pe-sql-prod", "type": "Microsoft.Network/privateEndpoints", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"privateLinkServiceConnections": [{"name": "plsc-sql", "properties": {"privateLinkServiceId": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-prod-01"}}]}, "tags": {}},
                                # LB with publicIPAddress reference
                                {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/loadBalancers/lb-web", "name": "lb-web", "type": "Microsoft.Network/loadBalancers", "location": "eastus", "resourceGroup": "rg-prod", "subscriptionId": "sub-1", "properties": {"frontendIPConfigurations": [{"name": "fe-public", "properties": {"publicIPAddress": {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/publicIPAddresses/pip-web-01"}}}]}, "tags": {}},
                            ],
                        },
                    },
                },
                "identity_access": {
                    "tools": {
                        "rg_identity_discovery": {
                            "status": "completed",
                            "resource_count": 2,
                            "resources": [
                                {"id": "/subscriptions/sub-1/providers/Microsoft.Authorization/roleAssignments/ra-001", "name": "ra-001", "type": "Microsoft.Authorization/roleAssignments", "subscriptionId": "sub-1", "properties": {"principalId": "user-001", "principalType": "User", "scope": "/subscriptions/sub-1"}},
                                {"id": "/subscriptions/sub-1/providers/Microsoft.Authorization/roleAssignments/ra-002", "name": "ra-002", "type": "Microsoft.Authorization/roleAssignments", "subscriptionId": "sub-1", "properties": {"principalId": "sp-deploy", "principalType": "ServicePrincipal", "scope": "/subscriptions/sub-1"}},
                            ],
                        },
                        "rg_policy_discovery": {
                            "status": "completed",
                            "resource_count": 1,
                            "resources": [
                                {"id": "/subscriptions/sub-1/providers/Microsoft.Authorization/policyAssignments/pa-tags", "name": "pa-tags", "type": "Microsoft.Authorization/policyAssignments", "subscriptionId": "sub-1", "properties": {"displayName": "Require tags", "scope": "/subscriptions/sub-1"}},
                            ],
                        },
                    },
                },
            },
        },
    }


# ====================== _collect_resources_from_layers ======================

class TestCollectResources:
    def test_collects_all_unique(self):
        disc = _make_stub_discovery()
        resources = _collect_resources_from_layers(disc["results"])
        ids = [r["id"] for r in resources]
        # 7 inventory + 2 unique topology (nic, pe, lb) + 2 duplicates deduped + 3 identity = 12 unique
        # Inventory: vm-web-01, vm-api-01, stproddata01, sql-prod-01, vnet-prod, nsg-web, app-frontend = 7
        # Topology unique: nic-vm-web-01, pe-sql-prod, lb-web = 3 new (vnet-prod and nsg-web are dupes)
        # Identity: ra-001, ra-002, pa-tags = 3
        assert len(resources) == 13  # 7 + 3 + 3

    def test_deduplication(self):
        disc = _make_stub_discovery()
        resources = _collect_resources_from_layers(disc["results"])
        ids = [r["id"] for r in resources]
        # vnet-prod should appear only once
        vnet_count = sum(1 for rid in ids if "vnet-prod" in rid)
        assert vnet_count == 1

    def test_prefers_more_properties(self):
        disc = _make_stub_discovery()
        resources = _collect_resources_from_layers(disc["results"])
        # nsg-web appears in both inventory (empty props) and topology (with securityRules)
        nsg = next(r for r in resources if "nsg-web" in r["id"])
        # Topology version has more properties, so should be preferred
        assert "securityRules" in nsg.get("properties", {})


# ====================== build_graph_from_discovery ======================

class TestBuildGraph:
    def test_returns_graph_data(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        assert graph.discovery_id == "disc-001"
        assert graph.tenant_id == "tenant-123"

    def test_has_tenant_node(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        tenant_nodes = [n for n in graph.nodes if n.label == "tenant"]
        assert len(tenant_nodes) == 1
        assert tenant_nodes[0].id == "tenant-123"

    def test_has_subscription_node(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        sub_nodes = [n for n in graph.nodes if n.label == "subscription"]
        assert len(sub_nodes) == 1
        assert sub_nodes[0].id == "sub-1"

    def test_has_resource_group_node(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        rg_nodes = [n for n in graph.nodes if n.label == "resource_group"]
        assert len(rg_nodes) == 1
        assert rg_nodes[0].name == "rg-prod"

    def test_resource_count(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        resource_nodes = [n for n in graph.nodes if n.label == "resource"]
        # 7 inventory + 3 unique topology + 3 identity = 13
        # But identity resources (ra-001, ra-002, pa-tags) don't have resourceGroup
        # so they won't be in rg-prod children (they're subscription-level)
        assert len(resource_nodes) >= 10  # at least the RG-level resources

    def test_contains_edges_form_tree(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        contains = [e for e in graph.edges if e.label == "contains"]
        # At least: tenant→sub, sub→rg, rg→each resource
        assert len(contains) >= 12  # 1 + 1 + 10 resources

    def test_hierarchy_structure(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        h = graph.hierarchy
        assert h["id"] == "tenant-123"
        assert h["label"] == "tenant"
        assert len(h["children"]) == 1  # one subscription
        sub = h["children"][0]
        assert sub["id"] == "sub-1"
        assert len(sub["children"]) >= 1  # at least rg-prod

    def test_stats(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        assert graph.stats["total_nodes"] > 0
        assert graph.stats["total_edges"] > 0
        assert "tenant" in graph.stats["nodes_by_type"]
        assert "subscription" in graph.stats["nodes_by_type"]
        assert "resource_group" in graph.stats["nodes_by_type"]
        assert "resource" in graph.stats["nodes_by_type"]


# ====================== Topology Edge Inference ======================

class TestTopologyEdges:
    def test_nic_to_vm_edge(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        nic_to_vm = [e for e in graph.edges if e.edge_type == "nic_to_vm"]
        assert len(nic_to_vm) >= 1
        edge = nic_to_vm[0]
        assert "nic-vm-web-01" in edge.source
        assert "vm-web-01" in edge.target

    def test_nic_to_nsg_edge(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        nic_to_nsg = [e for e in graph.edges if e.edge_type == "nic_to_nsg"]
        assert len(nic_to_nsg) >= 1

    def test_nic_to_subnet_edge(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        nic_to_subnet = [e for e in graph.edges if e.edge_type == "nic_to_subnet"]
        assert len(nic_to_subnet) >= 1
        # Should point to vnet-prod (subnet ID stripped to VNet)
        assert "vnet-prod" in nic_to_subnet[0].target

    def test_pe_to_target_edge(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        pe_edges = [e for e in graph.edges if e.edge_type == "pe_to_target"]
        assert len(pe_edges) >= 1
        assert "sql-prod-01" in pe_edges[0].target

    def test_no_edge_to_missing_target(self):
        """Edges should only be created when target exists in the graph."""
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        node_ids = {n.id for n in graph.nodes}
        for edge in graph.edges:
            if edge.label == "network_link":
                assert edge.target in node_ids, f"Edge target {edge.target} not in graph nodes"


# ====================== Identity Edge Inference ======================

class TestIdentityEdges:
    def test_role_assignment_edge(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        assigned = [e for e in graph.edges if e.label == "assigned_to"]
        # ra-001 and ra-002 scope to /subscriptions/sub-1 which is a node
        assert len(assigned) >= 2

    def test_policy_assignment_edge(self):
        disc = _make_stub_discovery()
        graph = build_graph_from_discovery(disc)
        governed = [e for e in graph.edges if e.label == "governed_by"]
        assert len(governed) >= 1
        assert governed[0].properties["displayName"] == "Require tags"


# ====================== Empty / Edge Cases ======================

class TestEdgeCases:
    def test_empty_discovery(self):
        disc = {"discovery_id": "empty", "tenant_id": "t-1", "results": {}}
        graph = build_graph_from_discovery(disc)
        # Should still have tenant node
        assert len(graph.nodes) == 1
        assert graph.nodes[0].label == "tenant"
        assert len(graph.edges) == 0

    def test_no_layers_key(self):
        disc = {"discovery_id": "empty", "tenant_id": "t-1", "results": {"inventory": {}}}
        graph = build_graph_from_discovery(disc)
        assert graph.discovery_id == "empty"

    def test_missing_results(self):
        disc = {"discovery_id": "x", "tenant_id": "t-1"}
        graph = build_graph_from_discovery(disc)
        assert len(graph.nodes) == 1  # just tenant

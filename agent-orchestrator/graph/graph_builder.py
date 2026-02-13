"""Build graph representation from discovery results.

Pure Python module — no Gremlin dependency. Transforms flat discovery
results into nodes + edges + hierarchy for the topology UI.
"""
import re
import uuid
from typing import Dict, List, Optional, Set, Tuple

from models import GraphData, GraphEdge, GraphNode

# ---------------------------------------------------------------------------
# Azure Resource ID parser
# ---------------------------------------------------------------------------

_RID_PATTERN = re.compile(
    r"^/subscriptions/(?P<subscription_id>[^/]+)"
    r"(/resourceGroups/(?P<resource_group>[^/]+))?"
    r"(/providers/(?P<provider_namespace>[^/]+)/(?P<resource_type>[^/]+)/(?P<name>.+))?$",
    re.IGNORECASE,
)


def parse_resource_id(resource_id: str) -> Dict:
    """Parse an Azure resource ID into its components.

    Handles:
      /subscriptions/{sub}
      /subscriptions/{sub}/resourceGroups/{rg}
      /subscriptions/{sub}/resourceGroups/{rg}/providers/{ns}/{type}/{name}
      /subscriptions/{sub}/providers/{ns}/{type}/{name}  (subscription-level resources)
    """
    m = _RID_PATTERN.match(resource_id)
    if not m:
        return {"raw": resource_id}
    return {
        "subscription_id": m.group("subscription_id"),
        "resource_group": m.group("resource_group"),
        "provider_namespace": m.group("provider_namespace"),
        "resource_type": m.group("resource_type"),
        "name": m.group("name"),
    }


# ---------------------------------------------------------------------------
# Topology edge inference rules
# ---------------------------------------------------------------------------

# Each rule: (source_type_suffix, property_path_extractor, edge_sub_type)
# property_path_extractor is a function: resource -> list of target IDs

def _get_nested(obj, *keys):
    """Safely traverse nested dict keys."""
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _nic_to_vm(res):
    vm = _get_nested(res, "properties", "virtualMachine", "id")
    return [vm] if vm else []


def _nic_to_nsg(res):
    nsg = _get_nested(res, "properties", "networkSecurityGroup", "id")
    return [nsg] if nsg else []


def _nic_to_subnet(res):
    targets = []
    ip_configs = _get_nested(res, "properties", "ipConfigurations") or []
    for ipc in ip_configs:
        subnet_id = _get_nested(ipc, "properties", "subnet", "id")
        if subnet_id:
            # Subnet IDs reference the parent VNet — extract VNet ID
            # Format: .../virtualNetworks/{vnet}/subnets/{subnet}
            parts = subnet_id.rsplit("/subnets/", 1)
            vnet_id = parts[0] if len(parts) == 2 else subnet_id
            targets.append(vnet_id)
    return targets


def _lb_to_pip(res):
    targets = []
    fe_configs = _get_nested(res, "properties", "frontendIPConfigurations") or []
    for fe in fe_configs:
        pip_id = _get_nested(fe, "properties", "publicIPAddress", "id")
        if pip_id:
            targets.append(pip_id)
    return targets


def _pe_to_target(res):
    targets = []
    pls_conns = _get_nested(res, "properties", "privateLinkServiceConnections") or []
    for conn in pls_conns:
        target_id = _get_nested(conn, "properties", "privateLinkServiceId")
        if target_id:
            targets.append(target_id)
    return targets


TOPOLOGY_RULES = [
    ("microsoft.network/networkinterfaces", _nic_to_vm, "nic_to_vm"),
    ("microsoft.network/networkinterfaces", _nic_to_nsg, "nic_to_nsg"),
    ("microsoft.network/networkinterfaces", _nic_to_subnet, "nic_to_subnet"),
    ("microsoft.network/loadbalancers", _lb_to_pip, "lb_to_pip"),
    ("microsoft.network/privateendpoints", _pe_to_target, "pe_to_target"),
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_resources_from_layers(results: Dict) -> List[Dict]:
    """Collect all resources from results.layers.*.tools.*.resources, deduplicated by id."""
    seen: Dict[str, Dict] = {}
    layers = results.get("layers", {})
    for layer_data in layers.values():
        tools = layer_data.get("tools", {}) if isinstance(layer_data, dict) else {}
        for tool_data in tools.values():
            if not isinstance(tool_data, dict):
                continue
            resources = tool_data.get("resources", [])
            for res in resources:
                rid = res.get("id")
                if rid and rid not in seen:
                    seen[rid] = res
                elif rid and rid in seen:
                    # Merge: prefer the version with more properties
                    existing = seen[rid]
                    if len(res.get("properties", {})) > len(existing.get("properties", {})):
                        seen[rid] = res
    return list(seen.values())


def _build_hierarchy(
    resources: List[Dict], tenant_id: str
) -> Tuple[List[GraphNode], List[GraphEdge], Dict]:
    """Build hierarchy nodes (tenant, subscription, resource_group) and contains edges.

    Returns (nodes, edges, hierarchy_dict) where hierarchy_dict is a nested
    tree structure for the UI tree panel.
    """
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    # Collect unique subscriptions and resource groups
    subscriptions: Dict[str, Set[str]] = {}  # sub_id -> set of rg names
    rg_locations: Dict[str, str] = {}  # "sub/rg" -> location
    resource_by_rg: Dict[str, List[Dict]] = {}  # "sub/rg" -> resources

    for res in resources:
        sub_id = res.get("subscriptionId") or ""
        rg = res.get("resourceGroup") or ""
        parsed = parse_resource_id(res.get("id", ""))
        if not sub_id:
            sub_id = parsed.get("subscription_id", "")
        if not rg:
            rg = parsed.get("resource_group", "")

        if sub_id:
            if sub_id not in subscriptions:
                subscriptions[sub_id] = set()
            if rg:
                subscriptions[sub_id].add(rg)
                rg_key = f"{sub_id}/resourceGroups/{rg}"
                if rg_key not in rg_locations:
                    rg_locations[rg_key] = res.get("location", "")
                if rg_key not in resource_by_rg:
                    resource_by_rg[rg_key] = []
                resource_by_rg[rg_key].append(res)

    # Tenant node
    nodes.append(GraphNode(
        id=tenant_id,
        label="tenant",
        name=f"Tenant {tenant_id[:8]}..." if len(tenant_id) > 8 else f"Tenant {tenant_id}",
        children_count=len(subscriptions),
    ))

    # Hierarchy dict for tree panel
    hierarchy = {
        "id": tenant_id,
        "label": "tenant",
        "name": nodes[-1].name,
        "children": [],
    }

    for sub_id, rg_names in sorted(subscriptions.items()):
        # Subscription node
        sub_node = GraphNode(
            id=sub_id,
            label="subscription",
            name=f"Subscription {sub_id[:8]}..." if len(sub_id) > 8 else f"Subscription {sub_id}",
            subscription_id=sub_id,
            children_count=len(rg_names),
        )
        nodes.append(sub_node)

        # Tenant → Subscription edge
        edges.append(GraphEdge(
            id=f"contains-{tenant_id}-{sub_id}",
            source=tenant_id,
            target=sub_id,
            label="contains",
        ))

        sub_tree = {
            "id": sub_id,
            "label": "subscription",
            "name": sub_node.name,
            "children": [],
        }
        hierarchy["children"].append(sub_tree)

        for rg in sorted(rg_names):
            rg_key = f"{sub_id}/resourceGroups/{rg}"
            rg_resources = resource_by_rg.get(rg_key, [])

            # Resource Group node
            rg_node = GraphNode(
                id=rg_key,
                label="resource_group",
                name=rg,
                subscription_id=sub_id,
                location=rg_locations.get(rg_key, ""),
                children_count=len(rg_resources),
            )
            nodes.append(rg_node)

            # Subscription → RG edge
            edges.append(GraphEdge(
                id=f"contains-{sub_id}-{rg}",
                source=sub_id,
                target=rg_key,
                label="contains",
            ))

            rg_tree = {
                "id": rg_key,
                "label": "resource_group",
                "name": rg,
                "children": [],
            }
            sub_tree["children"].append(rg_tree)

            for res in rg_resources:
                rid = res.get("id", "")
                res_name = res.get("name", rid.split("/")[-1] if "/" in rid else rid)
                res_type = res.get("type", "")

                # Resource node
                parsed = parse_resource_id(rid)
                nodes.append(GraphNode(
                    id=rid,
                    label="resource",
                    name=res_name,
                    type=res_type,
                    provider_namespace=parsed.get("provider_namespace"),
                    location=res.get("location"),
                    resource_group=rg,
                    subscription_id=sub_id,
                    properties=res.get("properties"),
                    tags=res.get("tags"),
                ))

                # RG → Resource edge
                edges.append(GraphEdge(
                    id=f"contains-{rg}-{res_name}",
                    source=rg_key,
                    target=rid,
                    label="contains",
                ))

                rg_tree["children"].append({
                    "id": rid,
                    "label": "resource",
                    "name": res_name,
                    "type": res_type,
                })

    return nodes, edges, hierarchy


def _infer_topology_edges(
    resources: List[Dict], node_ids: Set[str]
) -> List[GraphEdge]:
    """Apply topology rules to infer network relationship edges."""
    edges: List[GraphEdge] = []
    for res in resources:
        res_type = (res.get("type") or "").lower()
        res_id = res.get("id", "")
        for type_suffix, extractor, sub_type in TOPOLOGY_RULES:
            if res_type == type_suffix:
                targets = extractor(res)
                for target_id in targets:
                    # Only create edge if target exists in our graph
                    if target_id in node_ids:
                        edge_id = f"network-{sub_type}-{res.get('name', '')}-{target_id.split('/')[-1]}"
                        edges.append(GraphEdge(
                            id=edge_id,
                            source=res_id,
                            target=target_id,
                            label="network_link",
                            edge_type=sub_type,
                        ))
    return edges


def _resolve_scope_to_node_id(scope: str, node_ids: Set[str]) -> Optional[str]:
    """Resolve an Azure scope path to a graph node ID.

    Scope can be:
      /subscriptions/sub-1  →  node ID is 'sub-1'
      /subscriptions/sub-1/resourceGroups/rg-prod  →  node ID is 'sub-1/resourceGroups/rg-prod'
      full resource ID  →  node ID is the full path
    """
    if scope in node_ids:
        return scope
    # Try parsing as a resource ID and map to our node ID format
    parsed = parse_resource_id(scope)
    if "raw" in parsed:
        return None
    sub_id = parsed.get("subscription_id")
    rg = parsed.get("resource_group")
    if rg and sub_id:
        candidate = f"{sub_id}/resourceGroups/{rg}"
        if candidate in node_ids:
            return candidate
    if sub_id and sub_id in node_ids:
        return sub_id
    return None


def _infer_identity_edges(
    resources: List[Dict], node_ids: Set[str]
) -> List[GraphEdge]:
    """Parse role/policy assignments to create assigned_to/governed_by edges."""
    edges: List[GraphEdge] = []
    for res in resources:
        res_type = (res.get("type") or "").lower()
        res_id = res.get("id", "")
        scope = _get_nested(res, "properties", "scope") or ""

        if "roleassignments" in res_type and scope:
            target = _resolve_scope_to_node_id(scope, node_ids)
            if target:
                principal = _get_nested(res, "properties", "principalId") or "unknown"
                edges.append(GraphEdge(
                    id=f"assigned-{res.get('name', '')}-{target.split('/')[-1]}",
                    source=res_id,
                    target=target,
                    label="assigned_to",
                    edge_type="role_assignment",
                    properties={
                        "principalId": principal,
                        "principalType": _get_nested(res, "properties", "principalType") or "",
                    },
                ))

        elif "policyassignments" in res_type and scope:
            target = _resolve_scope_to_node_id(scope, node_ids)
            if target:
                edges.append(GraphEdge(
                    id=f"governed-{res.get('name', '')}-{target.split('/')[-1]}",
                    source=res_id,
                    target=target,
                    label="governed_by",
                    edge_type="policy_assignment",
                    properties={
                        "displayName": _get_nested(res, "properties", "displayName") or "",
                    },
                ))

    return edges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_graph_from_discovery(discovery: Dict) -> GraphData:
    """Build a complete graph representation from a discovery document.

    Args:
        discovery: Discovery document with results.layers structure.

    Returns:
        GraphData with nodes, edges, hierarchy tree, and stats.
    """
    discovery_id = discovery.get("discovery_id", "")
    tenant_id = discovery.get("tenant_id", "unknown")
    subscription_id = discovery.get("subscription_id")
    results = discovery.get("results", {})

    # 1. Collect all resources from all layers
    resources = _collect_resources_from_layers(results)

    # 2. Build hierarchy (tenant → sub → rg → resource) nodes + edges
    hierarchy_nodes, hierarchy_edges, hierarchy_tree = _build_hierarchy(resources, tenant_id)

    # 3. Build set of all node IDs for edge validation
    node_ids: Set[str] = {n.id for n in hierarchy_nodes}
    # Also add subscription IDs as targets for identity edges
    for res in resources:
        sub = res.get("subscriptionId")
        if sub:
            node_ids.add(sub)

    # 4. Infer topology edges
    topo_edges = _infer_topology_edges(resources, node_ids)

    # 5. Infer identity/policy edges
    identity_edges = _infer_identity_edges(resources, node_ids)

    # 6. Combine
    all_edges = hierarchy_edges + topo_edges + identity_edges

    # 7. Compute stats
    type_counts: Dict[str, int] = {}
    for n in hierarchy_nodes:
        type_counts[n.label] = type_counts.get(n.label, 0) + 1

    edge_label_counts: Dict[str, int] = {}
    for e in all_edges:
        edge_label_counts[e.label] = edge_label_counts.get(e.label, 0) + 1

    stats = {
        "total_nodes": len(hierarchy_nodes),
        "total_edges": len(all_edges),
        "nodes_by_type": type_counts,
        "edges_by_label": edge_label_counts,
        "resource_count": type_counts.get("resource", 0),
    }

    return GraphData(
        nodes=hierarchy_nodes,
        edges=all_edges,
        hierarchy=hierarchy_tree,
        stats=stats,
        discovery_id=discovery_id,
        tenant_id=tenant_id,
        subscription_id=subscription_id,
    )

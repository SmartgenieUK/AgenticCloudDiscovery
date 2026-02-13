"""Discovery layer definitions, registry, and dependency resolution.

Each discovery layer represents a concern-based view of an Azure subscription:
  Layer 1: Inventory — What exists
  Layer 2: Topology — How it's connected
  Layer 3: Identity & Access — Who can do what
  Layer 4: Data Flow — How data moves (scaffold)
  Layer 5: Dependencies — What relies on what (scaffold)
  Layer 6: Governance — How well managed (scaffold)
  Layer 7: HA/DR — How resilient (scaffold)
  Layer 8: Operations & Cost — How it's run (scaffold)
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class LayerDefinition:
    """Declarative definition of a single discovery layer."""
    layer_id: str
    layer_number: int
    label: str
    description: str
    depends_on: List[str] = field(default_factory=list)
    collection_tool_ids: List[str] = field(default_factory=list)
    collection_uses_ai: bool = False
    analysis_uses_ai: bool = True
    enabled: bool = True


# ====================== Layer Registry ======================

LAYER_REGISTRY: Dict[str, LayerDefinition] = {}


def _register(layer: LayerDefinition) -> None:
    LAYER_REGISTRY[layer.layer_id] = layer


# Layer 1: Inventory — What exists (single Resource Graph query)
_register(LayerDefinition(
    layer_id="inventory",
    layer_number=1,
    label="Inventory",
    description="What exists in this subscription",
    depends_on=[],
    collection_tool_ids=[
        "rg_inventory_discovery",
    ],
    collection_uses_ai=False,
))

# Layer 2: Topology — How it's connected (single Resource Graph query)
_register(LayerDefinition(
    layer_id="topology",
    layer_number=2,
    label="Topology",
    description="How resources are connected",
    depends_on=["inventory"],
    collection_tool_ids=[
        "rg_topology_discovery",
    ],
    collection_uses_ai=False,
))

# Layer 3: Identity & Access — Who can do what (2 Resource Graph queries)
_register(LayerDefinition(
    layer_id="identity_access",
    layer_number=3,
    label="Identity & Access",
    description="Who can do what",
    depends_on=["inventory"],
    collection_tool_ids=[
        "rg_identity_discovery",
        "rg_policy_discovery",
    ],
    collection_uses_ai=False,
))

# Layer 4: Data Flow (scaffold)
_register(LayerDefinition(
    layer_id="data_flow",
    layer_number=4,
    label="Data Flow",
    description="How data moves between resources",
    depends_on=["inventory", "topology"],
    collection_tool_ids=[],
    collection_uses_ai=True,
    enabled=False,
))

# Layer 5: Dependencies (scaffold)
_register(LayerDefinition(
    layer_id="dependencies",
    layer_number=5,
    label="Dependencies",
    description="Runtime and configuration dependencies",
    depends_on=["inventory", "topology"],
    collection_tool_ids=[],
    collection_uses_ai=True,
    enabled=False,
))

# Layer 6: Governance (scaffold)
_register(LayerDefinition(
    layer_id="governance",
    layer_number=6,
    label="Governance",
    description="Policy compliance and tagging standards",
    depends_on=["inventory"],
    collection_tool_ids=[],
    collection_uses_ai=False,
    enabled=False,
))

# Layer 7: HA/DR (scaffold)
_register(LayerDefinition(
    layer_id="ha_dr",
    layer_number=7,
    label="HA/DR",
    description="High availability and disaster recovery posture",
    depends_on=["inventory", "topology"],
    collection_tool_ids=[],
    collection_uses_ai=False,
    enabled=False,
))

# Layer 8: Operations & Cost (scaffold)
_register(LayerDefinition(
    layer_id="operations_cost",
    layer_number=8,
    label="Operations & Cost",
    description="Operational health and cost optimization",
    depends_on=["inventory"],
    collection_tool_ids=["cost_discovery"],
    collection_uses_ai=False,
    enabled=False,
))


# ====================== Dependency Resolution ======================

def resolve_layer_dependencies(requested_layer_ids: List[str]) -> List[str]:
    """Resolve all dependencies and return an ordered list sorted by layer_number.

    Example: ["topology"] -> ["inventory", "topology"]
    Raises ValueError for unknown layer IDs.
    """
    resolved: Set[str] = set()

    def _resolve(layer_id: str) -> None:
        if layer_id in resolved:
            return
        layer_def = LAYER_REGISTRY.get(layer_id)
        if not layer_def:
            raise ValueError(f"Unknown layer: {layer_id}")
        for dep in layer_def.depends_on:
            _resolve(dep)
        resolved.add(layer_id)

    for lid in requested_layer_ids:
        _resolve(lid)

    return sorted(resolved, key=lambda lid: LAYER_REGISTRY[lid].layer_number)


def get_enabled_layers() -> List[LayerDefinition]:
    """Return all enabled layers, sorted by layer_number."""
    return sorted(
        [layer for layer in LAYER_REGISTRY.values() if layer.enabled],
        key=lambda layer: layer.layer_number,
    )

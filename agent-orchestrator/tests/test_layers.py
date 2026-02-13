"""Unit tests for the discovery layer framework."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from discoveries.layers import (
    LAYER_REGISTRY,
    LayerDefinition,
    get_enabled_layers,
    resolve_layer_dependencies,
)


# ====================== Registry Well-Formedness ======================

class TestLayerRegistry:
    def test_all_layers_have_unique_ids(self):
        ids = [layer.layer_id for layer in LAYER_REGISTRY.values()]
        assert len(ids) == len(set(ids))

    def test_all_layers_have_unique_numbers(self):
        numbers = [layer.layer_number for layer in LAYER_REGISTRY.values()]
        assert len(numbers) == len(set(numbers))

    def test_layer_numbers_are_1_through_8(self):
        numbers = sorted(layer.layer_number for layer in LAYER_REGISTRY.values())
        assert numbers == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_all_dependencies_reference_valid_layers(self):
        for layer in LAYER_REGISTRY.values():
            for dep in layer.depends_on:
                assert dep in LAYER_REGISTRY, f"{layer.layer_id} depends on unknown layer {dep}"

    def test_no_self_dependencies(self):
        for layer in LAYER_REGISTRY.values():
            assert layer.layer_id not in layer.depends_on, f"{layer.layer_id} depends on itself"

    def test_dependencies_have_lower_layer_numbers(self):
        for layer in LAYER_REGISTRY.values():
            for dep in layer.depends_on:
                dep_layer = LAYER_REGISTRY[dep]
                assert dep_layer.layer_number < layer.layer_number, (
                    f"{layer.layer_id} (L{layer.layer_number}) depends on "
                    f"{dep} (L{dep_layer.layer_number}) which has equal or higher number"
                )

    def test_registry_has_8_layers(self):
        assert len(LAYER_REGISTRY) == 8

    def test_layer_1_is_inventory(self):
        inv = LAYER_REGISTRY["inventory"]
        assert inv.layer_number == 1
        assert inv.enabled is True
        assert inv.depends_on == []

    def test_layer_2_is_topology(self):
        topo = LAYER_REGISTRY["topology"]
        assert topo.layer_number == 2
        assert topo.enabled is True
        assert "inventory" in topo.depends_on

    def test_layer_3_is_identity_access(self):
        ia = LAYER_REGISTRY["identity_access"]
        assert ia.layer_number == 3
        assert ia.enabled is True
        assert "inventory" in ia.depends_on

    def test_inventory_has_expected_tools(self):
        inv = LAYER_REGISTRY["inventory"]
        assert "rg_inventory_discovery" in inv.collection_tool_ids
        assert len(inv.collection_tool_ids) == 1

    def test_topology_has_expected_tools(self):
        topo = LAYER_REGISTRY["topology"]
        assert "rg_topology_discovery" in topo.collection_tool_ids
        assert len(topo.collection_tool_ids) == 1

    def test_identity_has_expected_tools(self):
        ia = LAYER_REGISTRY["identity_access"]
        assert "rg_identity_discovery" in ia.collection_tool_ids
        assert "rg_policy_discovery" in ia.collection_tool_ids
        assert len(ia.collection_tool_ids) == 2


# ====================== Dependency Resolution ======================

class TestResolveDependencies:
    def test_single_layer_no_deps(self):
        result = resolve_layer_dependencies(["inventory"])
        assert result == ["inventory"]

    def test_layer_with_one_dep(self):
        result = resolve_layer_dependencies(["topology"])
        assert result == ["inventory", "topology"]

    def test_layer_with_shared_dep(self):
        result = resolve_layer_dependencies(["topology", "identity_access"])
        assert result == ["inventory", "topology", "identity_access"]

    def test_explicit_plus_dep(self):
        result = resolve_layer_dependencies(["inventory", "topology"])
        assert result == ["inventory", "topology"]

    def test_all_three_enabled(self):
        result = resolve_layer_dependencies(["inventory", "topology", "identity_access"])
        assert result == ["inventory", "topology", "identity_access"]

    def test_maintains_order_by_layer_number(self):
        # Request in reverse order — should still come out sorted
        result = resolve_layer_dependencies(["identity_access", "topology", "inventory"])
        assert result == ["inventory", "topology", "identity_access"]

    def test_transitive_deps(self):
        # data_flow depends on inventory + topology
        result = resolve_layer_dependencies(["data_flow"])
        assert result == ["inventory", "topology", "data_flow"]

    def test_unknown_layer_raises(self):
        with pytest.raises(ValueError, match="Unknown layer: bogus"):
            resolve_layer_dependencies(["bogus"])

    def test_empty_list(self):
        result = resolve_layer_dependencies([])
        assert result == []

    def test_idempotent(self):
        result = resolve_layer_dependencies(["inventory", "inventory"])
        assert result == ["inventory"]

    def test_deep_chain(self):
        # ha_dr depends on inventory + topology
        result = resolve_layer_dependencies(["ha_dr"])
        assert result == ["inventory", "topology", "ha_dr"]


# ====================== Get Enabled Layers ======================

class TestGetEnabledLayers:
    def test_returns_only_enabled(self):
        enabled = get_enabled_layers()
        for layer in enabled:
            assert layer.enabled is True

    def test_sorted_by_layer_number(self):
        enabled = get_enabled_layers()
        numbers = [layer.layer_number for layer in enabled]
        assert numbers == sorted(numbers)

    def test_currently_3_enabled(self):
        enabled = get_enabled_layers()
        assert len(enabled) == 3
        assert [l.layer_id for l in enabled] == ["inventory", "topology", "identity_access"]

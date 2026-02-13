import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import ResourceNode from "./ResourceNode";

const nodeTypes = { resource: ResourceNode };

// Row ordering for layout: lower row = higher in diagram
const TYPE_ROW = {
  "microsoft.network/virtualnetworks": 0,
  "microsoft.network/networksecuritygroups": 1,
  "microsoft.network/routetables": 1,
  "microsoft.compute/virtualmachines": 2,
  "microsoft.web/sites": 2,
  "microsoft.sql/servers": 2,
  "microsoft.dbformysql/servers": 2,
  "microsoft.dbforpostgresql/servers": 2,
  "microsoft.keyvault/vaults": 2,
  "microsoft.network/networkinterfaces": 3,
  "microsoft.network/loadbalancers": 3,
  "microsoft.network/privateendpoints": 3,
  "microsoft.network/publicipaddresses": 4,
  "microsoft.compute/disks": 4,
  "microsoft.storage/storageaccounts": 4,
  "microsoft.authorization/roleassignments": 5,
  "microsoft.authorization/roledefinitions": 5,
  "microsoft.authorization/policyassignments": 5,
};

const NODE_WIDTH = 190;
const NODE_HEIGHT = 70;
const H_GAP = 240;
const V_GAP = 140;

function layoutNodes(graphNodes, scopeId) {
  // Filter to resources within the selected scope (or all if no scope)
  let filtered = graphNodes.filter((n) => n.label === "resource");
  if (scopeId) {
    filtered = filtered.filter(
      (n) =>
        n.subscription_id === scopeId ||
        n.resource_group === scopeId ||
        (n.id && n.id.includes(scopeId))
    );
  }

  // Group by row
  const rows = {};
  for (const node of filtered) {
    const typeKey = (node.type || "").toLowerCase();
    const row = TYPE_ROW[typeKey] ?? 3;
    if (!rows[row]) rows[row] = [];
    rows[row].push(node);
  }

  // Assign positions
  const rfNodes = [];
  const sortedRows = Object.keys(rows).sort((a, b) => Number(a) - Number(b));

  for (const rowIdx of sortedRows) {
    const rowNodes = rows[rowIdx];
    const y = Number(rowIdx) * V_GAP;
    const startX = -((rowNodes.length - 1) * H_GAP) / 2;

    for (let i = 0; i < rowNodes.length; i++) {
      const n = rowNodes[i];
      rfNodes.push({
        id: n.id,
        type: "resource",
        position: { x: startX + i * H_GAP, y },
        data: {
          name: n.name,
          type: n.type,
          provider_namespace: n.provider_namespace,
          location: n.location,
        },
      });
    }
  }
  return rfNodes;
}

function layoutEdges(graphEdges, nodeIdSet, edgeFilter) {
  return graphEdges
    .filter((e) => edgeFilter.has(e.label))
    .filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.edge_type || e.label,
      type: "smoothstep",
      animated: e.label === "network_link",
      style: {
        stroke:
          e.label === "network_link"
            ? "#00a4ef"
            : e.label === "assigned_to"
            ? "#64748b"
            : e.label === "governed_by"
            ? "#d97706"
            : "#94a3b8",
        strokeWidth: e.label === "network_link" ? 2 : 1,
      },
    }));
}

const TopologyCanvas = ({ graph, scopeId, edgeFilter, onNodeClick }) => {
  const rfNodesInit = useMemo(
    () => layoutNodes(graph?.nodes || [], scopeId),
    [graph, scopeId]
  );

  const nodeIdSet = useMemo(
    () => new Set(rfNodesInit.map((n) => n.id)),
    [rfNodesInit]
  );

  const rfEdgesInit = useMemo(
    () => layoutEdges(graph?.edges || [], nodeIdSet, edgeFilter),
    [graph, nodeIdSet, edgeFilter]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodesInit);
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdgesInit);

  // Sync when inputs change
  useMemo(() => {
    setNodes(rfNodesInit);
    setEdges(rfEdgesInit);
  }, [rfNodesInit, rfEdgesInit, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_event, node) => {
      if (onNodeClick) {
        const graphNode = (graph?.nodes || []).find((n) => n.id === node.id);
        if (graphNode) onNodeClick(graphNode);
      }
    },
    [graph, onNodeClick]
  );

  if (!rfNodesInit.length) {
    return (
      <div className="canvas-empty">
        <p className="muted">Select a scope from the tree to view topology</p>
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.1}
      maxZoom={2}
      defaultEdgeOptions={{ type: "smoothstep" }}
    >
      <Background color="#e2e8f0" gap={20} />
      <Controls />
      <MiniMap
        nodeStrokeWidth={3}
        nodeColor={(n) => {
          const ns = n.data?.provider_namespace;
          if (ns === "Microsoft.Compute") return "#0078d4";
          if (ns === "Microsoft.Network") return "#00a4ef";
          if (ns === "Microsoft.Storage") return "#47b881";
          return "#94a3b8";
        }}
        zoomable
        pannable
      />
    </ReactFlow>
  );
};

export default TopologyCanvas;

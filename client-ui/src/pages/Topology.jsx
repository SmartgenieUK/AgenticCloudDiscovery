import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import TopologyTree from "../components/TopologyTree";
import TopologyCanvas from "../components/TopologyCanvas";
import TopologyDetail from "../components/TopologyDetail";

const DEFAULT_EDGE_FILTER = new Set(["contains", "network_link", "assigned_to", "governed_by"]);
const EDGE_TYPES = ["contains", "network_link", "assigned_to", "governed_by"];

const Topology = () => {
  const { discoveryId } = useParams();
  const navigate = useNavigate();

  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedScope, setSelectedScope] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [edgeFilter, setEdgeFilter] = useState(DEFAULT_EDGE_FILTER);

  useEffect(() => {
    if (!discoveryId) return;
    setLoading(true);
    setError("");
    api
      .getDiscoveryGraph(discoveryId)
      .then((data) => {
        setGraph(data);
        // Default scope: first subscription
        if (data.hierarchy?.children?.length > 0) {
          const firstSub = data.hierarchy.children[0];
          setSelectedScope(firstSub);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [discoveryId]);

  const handleTreeSelect = useCallback(
    (node) => {
      setSelectedScope(node);
      // If clicking a resource, also show detail
      if (node.label === "resource") {
        const fullNode = graph?.nodes?.find((n) => n.id === node.id);
        if (fullNode) setSelectedNode(fullNode);
      }
    },
    [graph]
  );

  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
  }, []);

  const toggleEdge = useCallback((edgeType) => {
    setEdgeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(edgeType)) {
        next.delete(edgeType);
      } else {
        next.add(edgeType);
      }
      return next;
    });
  }, []);

  const scopeId = useMemo(() => {
    if (!selectedScope) return null;
    // For subscription/rg nodes, use their ID for scoping
    if (selectedScope.label === "resource_group") {
      // Extract the RG name from the tree node
      return selectedScope.name;
    }
    return selectedScope.id;
  }, [selectedScope]);

  const stats = graph?.stats || {};

  if (loading) {
    return (
      <div className="topology-shell">
        <div className="topology-loading">
          <p>Loading topology...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="topology-shell">
        <div className="topology-error">
          <p className="error">{error}</p>
          <button className="secondary" onClick={() => navigate(-1)}>Go Back</button>
        </div>
      </div>
    );
  }

  return (
    <div className="topology-shell">
      {/* Header bar */}
      <div className="topology-header">
        <div className="topology-header-left">
          <button className="secondary topology-back" onClick={() => navigate(-1)}>
            Back
          </button>
          <h2 className="topology-title">Topology Explorer</h2>
          <span className="topology-stats">
            {stats.resource_count || 0} resources | {stats.total_edges || 0} relationships
          </span>
        </div>
        <div className="topology-toolbar">
          {EDGE_TYPES.map((et) => (
            <label key={et} className="edge-filter-toggle">
              <input
                type="checkbox"
                checked={edgeFilter.has(et)}
                onChange={() => toggleEdge(et)}
              />
              <span>{et.replace("_", " ")}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Three-panel layout */}
      <div className="topology-layout">
        {/* Left: Tree */}
        <div className="topology-tree-panel">
          <div className="panel-title">Hierarchy</div>
          <TopologyTree
            hierarchy={graph?.hierarchy}
            selectedId={selectedScope?.id}
            onSelect={handleTreeSelect}
          />
        </div>

        {/* Center: Canvas */}
        <div className="topology-canvas-panel">
          <TopologyCanvas
            graph={graph}
            scopeId={scopeId}
            edgeFilter={edgeFilter}
            onNodeClick={handleNodeClick}
          />
        </div>

        {/* Right: Detail */}
        <div className="topology-detail-panel">
          <div className="panel-title">Details</div>
          <TopologyDetail node={selectedNode} edges={graph?.edges} />
        </div>
      </div>
    </div>
  );
};

export default Topology;

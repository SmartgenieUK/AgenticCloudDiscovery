import { memo, useState } from "react";

const TopologyDetail = memo(({ node, edges }) => {
  const [showProps, setShowProps] = useState(false);

  if (!node) {
    return (
      <div className="detail-empty">
        <p className="muted">Select a resource to view details</p>
      </div>
    );
  }

  const connections = edges
    ? edges.filter((e) => e.source === node.id || e.target === node.id)
    : [];

  return (
    <div className="topology-detail">
      <div className="detail-header">
        <h3 className="detail-name">{node.name}</h3>
        <span className="detail-label-badge">{node.label}</span>
      </div>

      <div className="detail-section">
        {node.type && (
          <div className="detail-row">
            <span className="detail-key">Type</span>
            <span className="detail-value">{node.type}</span>
          </div>
        )}
        {node.location && (
          <div className="detail-row">
            <span className="detail-key">Location</span>
            <span className="detail-value">{node.location}</span>
          </div>
        )}
        {node.resource_group && (
          <div className="detail-row">
            <span className="detail-key">Resource Group</span>
            <span className="detail-value">{node.resource_group}</span>
          </div>
        )}
        {node.subscription_id && (
          <div className="detail-row">
            <span className="detail-key">Subscription</span>
            <span className="detail-value">{node.subscription_id}</span>
          </div>
        )}
        {node.provider_namespace && (
          <div className="detail-row">
            <span className="detail-key">Provider</span>
            <span className="detail-value">{node.provider_namespace}</span>
          </div>
        )}
        {node.children_count > 0 && (
          <div className="detail-row">
            <span className="detail-key">Children</span>
            <span className="detail-value">{node.children_count}</span>
          </div>
        )}
      </div>

      {node.tags && Object.keys(node.tags).length > 0 && (
        <div className="detail-section">
          <h4 className="detail-section-title">Tags</h4>
          {Object.entries(node.tags).map(([k, v]) => (
            <div key={k} className="detail-row">
              <span className="detail-key">{k}</span>
              <span className="detail-value">{v}</span>
            </div>
          ))}
        </div>
      )}

      {connections.length > 0 && (
        <div className="detail-section">
          <h4 className="detail-section-title">Connections ({connections.length})</h4>
          {connections.map((edge) => {
            const isSource = edge.source === node.id;
            return (
              <div key={edge.id} className="detail-connection">
                <span className={`detail-edge-label detail-edge-${edge.label}`}>
                  {edge.edge_type || edge.label}
                </span>
                <span className="detail-edge-dir">{isSource ? "\u2192" : "\u2190"}</span>
                <span className="detail-edge-target" title={isSource ? edge.target : edge.source}>
                  {(isSource ? edge.target : edge.source).split("/").pop()}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {node.properties && Object.keys(node.properties).length > 0 && (
        <div className="detail-section">
          <button
            className="secondary detail-props-toggle"
            onClick={() => setShowProps((v) => !v)}
          >
            {showProps ? "Hide" : "Show"} Properties
          </button>
          {showProps && (
            <pre className="detail-json">
              {JSON.stringify(node.properties, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
});

TopologyDetail.displayName = "TopologyDetail";
export default TopologyDetail;

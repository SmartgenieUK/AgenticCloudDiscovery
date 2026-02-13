import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import AgentStepper from "../components/AgentStepper";
import DevConsole, { ts } from "../components/DevConsole";

const Discovery = () => {
  const navigate = useNavigate();
  const [connections, setConnections] = useState([]);
  const [form, setForm] = useState({
    connection_id: "",
    tenant_id: "",
    subscription_id: "",
    message: "Run discovery for the selected scope.",
  });
  const [plan, setPlan] = useState(null);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newConn, setNewConn] = useState({
    tenant_id: "7f520e65-937e-49bd-b387-74d75cdf054b",
    subscription_ids: "67092ad3-497d-4455-8bea-4d7a4ed42344",
    provider: "managed_identity",
    client_id: "",
    client_secret: "",
  });
  const [availableLayers, setAvailableLayers] = useState([]);
  const [selectedLayers, setSelectedLayers] = useState(["inventory"]);
  const [logs, setLogs] = useState([]);
  const [showRaw, setShowRaw] = useState(false);

  const log = useCallback((level, message) => {
    setLogs((prev) => [...prev, { time: ts(), level, message }]);
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  const selectedConnection = useMemo(
    () => connections.find((c) => c.connection_id === form.connection_id),
    [connections, form.connection_id],
  );

  // Load connections and layers with retry (orchestrator may still be starting)
  useEffect(() => {
    let cancelled = false;
    const loadWithRetry = async (label, fn, onSuccess, onError, retries = 3, delay = 2000) => {
      for (let i = 0; i <= retries; i++) {
        if (cancelled) return;
        try {
          const data = await fn();
          if (!cancelled) onSuccess(data);
          return;
        } catch {
          if (i < retries) {
            await new Promise((r) => setTimeout(r, delay));
          } else if (!cancelled) {
            onError();
          }
        }
      }
    };

    log("info", "Loading connections...");
    loadWithRetry(
      "connections",
      () => api.listConnections(),
      (data) => {
        setConnections(data);
        if (data.length > 0) {
          setForm((prev) => ({
            ...prev,
            connection_id: data[0].connection_id,
            tenant_id: data[0].tenant_id || "",
          }));
          log("success", `Loaded ${data.length} connection(s)`);
        } else {
          log("warn", "No connections found. Create one to get started.");
        }
      },
      () => {
        setError("Unable to load connections.");
        log("error", "Failed to load connections from orchestrator");
      },
    );

    loadWithRetry(
      "layers",
      () => api.listLayers(),
      (data) => {
        setAvailableLayers(data);
        log("info", `Loaded ${data.length} discovery layers (${data.filter((l) => l.enabled).length} enabled)`);
      },
      () => log("warn", "Failed to load layers — layer selection disabled"),
    );

    return () => { cancelled = true; };
  }, []);

  const handleLayerToggle = useCallback((layerId) => {
    setSelectedLayers((prev) => {
      if (prev.includes(layerId)) {
        // Uncheck: also remove layers that depend on this one
        const removed = new Set([layerId]);
        let changed = true;
        while (changed) {
          changed = false;
          for (const layer of availableLayers) {
            if (!removed.has(layer.layer_id) && prev.includes(layer.layer_id)) {
              if (layer.depends_on.some((dep) => removed.has(dep))) {
                removed.add(layer.layer_id);
                changed = true;
              }
            }
          }
        }
        return prev.filter((id) => !removed.has(id));
      } else {
        // Check: auto-resolve dependencies
        const next = new Set(prev);
        const toResolve = [layerId];
        while (toResolve.length > 0) {
          const current = toResolve.pop();
          if (!next.has(current)) {
            next.add(current);
            const layer = availableLayers.find((l) => l.layer_id === current);
            if (layer) {
              for (const dep of layer.depends_on) {
                if (!next.has(dep)) toResolve.push(dep);
              }
            }
          }
        }
        // Sort by layer_number
        const layerOrder = {};
        for (const l of availableLayers) layerOrder[l.layer_id] = l.layer_number;
        return [...next].sort((a, b) => (layerOrder[a] || 0) - (layerOrder[b] || 0));
      }
    });
  }, [availableLayers]);

  const handleRun = async (e) => {
    e.preventDefault();
    setError("");
    setPlan(null);
    setResponse(null);
    setShowRaw(false);
    setLoading(true);

    const conn = connections.find((c) => c.connection_id === form.connection_id);
    log("info", "--- Discovery run started ---");
    log("info", `Connection: ${conn?.tenant_id || form.connection_id} (${conn?.provider || "?"})`);
    log("info", `Tenant: ${form.tenant_id || "(from connection)"} | Sub: ${form.subscription_id || "(all)"}`);

    // Simulate agent stage progress while request is in flight
    log("info", "[1/6] Validate: checking connection scope...");
    const t1 = setTimeout(() => log("info", "[2/6] Inventory: scanning all resources..."), 700);
    const t2 = setTimeout(() => log("info", "[3/6] Agents: dispatching service category agents..."), 1400);
    const t3 = setTimeout(() => log("info", "[4/6] Agents: processing category results..."), 2800);
    const t4 = setTimeout(() => log("info", "[5/6] Aggregate: combining results..."), 4200);
    const t5 = setTimeout(() => log("info", "[6/6] Persist: saving discovery snapshot..."), 5000);

    try {
      const payload = {
        connection_id: form.connection_id,
        tenant_id: form.tenant_id || undefined,
        subscription_id: form.subscription_id || undefined,
        message: form.message,
        layers: selectedLayers.length > 0 ? selectedLayers : undefined,
      };
      log("info", `POST /chat ${JSON.stringify({ connection_id: payload.connection_id.slice(0, 8) + "...", layers: payload.layers })}`);

      const data = await api.chat(payload);
      console.log("[Discovery] Full response:", data);
      setPlan(data.plan);
      setResponse(data);

      log("success", `Discovery completed: ${data.final_response}`);
      log("info", `trace_id: ${data.trace_id}`);
      log("info", `correlation_id: ${data.correlation_id}`);
      log("info", `session_id: ${data.session_id}`);
      log("info", `discovery_id: ${data.discovery?.discovery_id || "?"}`);
      log("info", `status: ${data.discovery?.status || "?"} | stage: ${data.discovery?.stage || "?"}`);

      // Log KQL queries from layer plan steps
      if (data.layer_plan) {
        data.layer_plan.forEach((lp) => {
          log("info", `Layer [${lp.label}]: ${lp.status} (${lp.steps?.length || 0} tools)`);
          (lp.steps || []).forEach((step) => {
            if (step.detail?.kql_query) {
              log("info", `KQL [${step.label || step.name}]:`);
              log("info", `  ${step.detail.kql_query}`);
            }
            if (step.detail?.resource_count != null) {
              log("info", `  -> ${step.detail.resource_count} resources returned`);
            }
            if (step.detail?.error) {
              log("error", `  -> Error: ${step.detail.error}`);
            }
          });
        });
      }

      // Log resource type breakdown from inventory
      if (data.discovery?.results?.inventory?.resources) {
        const typeCounts = {};
        data.discovery.results.inventory.resources.forEach((r) => {
          const t = r.type || "unknown";
          typeCounts[t] = (typeCounts[t] || 0) + 1;
        });
        log("info", `Resource types discovered:`);
        Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).forEach(([t, c]) => {
          log("info", `  ${t}: ${c}`);
        });
      }

      // Log service categories (dynamic — derived from actual resources found)
      if (data.discovery?.results?.categories) {
        const cats = Object.entries(data.discovery.results.categories)
          .sort((a, b) => b[1].resource_count - a[1].resource_count);
        log("info", `Service categories (${cats.length}):`);
        cats.forEach(([ns, cat]) => {
          log("success", `  ${cat.label || ns}: ${cat.resource_count} resources`);
        });
      }

      if (data.plan) {
        data.plan.forEach((step) => {
          const detail = step.detail ? ` ${JSON.stringify(step.detail)}` : "";
          const level = step.status === "completed" ? "success" : step.status === "skipped" ? "warn" : "error";
          log(level, `  Stage [${step.label || step.name}]: ${step.status}${detail}`);
        });
      }
    } catch (err) {
      setError(err.message);
      log("error", `Discovery failed: ${err.message}`);
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
      setLoading(false);
      log("info", "--- Discovery run ended ---");
    }
  };

  const handleCreateConnection = async () => {
    setError("");
    setCreating(true);
    log("info", "Connecting to Azure...");
    try {
      const payload = {
        tenant_id: newConn.tenant_id,
        subscription_ids: newConn.subscription_ids.split(",").map((s) => s.trim()).filter(Boolean),
        provider: newConn.provider,
      };
      if (payload.subscription_ids.length === 0) {
        throw new Error("Enter at least one subscription id.");
      }
      if (newConn.provider === "service_principal") {
        if (!newConn.client_id || !newConn.client_secret) {
          throw new Error("Client ID and Client Secret are required for Service Principal.");
        }
        payload.client_id = newConn.client_id;
        payload.client_secret = newConn.client_secret;
      }
      log("info", `Tenant: ${payload.tenant_id} | Subs: ${payload.subscription_ids.join(", ")} | Provider: ${payload.provider}`);

      const created = await api.createConnection(payload);
      const updated = [...connections, created];
      setConnections(updated);
      setForm((prev) => ({
        ...prev,
        connection_id: created.connection_id,
        tenant_id: created.tenant_id || "",
      }));
      log("success", `Azure connection created: ${created.connection_id}`);
      if (created.display_name) {
        log("success", `Authenticated as: ${created.display_name}`);
      }
    } catch (err) {
      setError(err.message);
      log("error", `Connection failed: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  // Extract category results for display
  const categoryResults = response?.discovery?.results?.categories || null;

  return (
    <div className="discovery-shell">
      {/* Header */}
      <div className="discovery-header">
        <div>
          <h1 className="form-title" style={{ marginBottom: "4px" }}>Discovery Console</h1>
          <p className="muted" style={{ margin: 0 }}>Run agent-based discovery across Azure service categories.</p>
        </div>
        <button className="secondary" onClick={() => navigate("/dashboard")}>
          Back
        </button>
      </div>

      <div className="discovery-layout">
        {/* Left column: controls */}
        <div className="discovery-controls">
          {/* Create connection */}
          <div className="card" style={{ marginTop: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h3 style={{ margin: 0 }}>Connect to Azure</h3>
            {connections.length > 0 && (
              <span className="stepper-badge stepper-badge-done" style={{ fontSize: "11px" }}>
                {connections[connections.length - 1].display_name
                  ? `Connected as ${connections[connections.length - 1].display_name}`
                  : `Connected (${connections[connections.length - 1].provider})`}
              </span>
            )}
          </div>
            <div className="grid-2">
              <div>
                <label htmlFor="conn-tenant">Tenant ID</label>
                <input
                  id="conn-tenant"
                  value={newConn.tenant_id}
                  onChange={(e) => setNewConn({ ...newConn, tenant_id: e.target.value })}
                  placeholder="e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>
              <div>
                <label htmlFor="conn-subs">Subscription IDs (comma separated)</label>
                <input
                  id="conn-subs"
                  value={newConn.subscription_ids}
                  onChange={(e) => setNewConn({ ...newConn, subscription_ids: e.target.value })}
                  placeholder="e.g. sub-id-1, sub-id-2"
                />
              </div>
            </div>
            <div className="grid-2">
              <div>
                <label htmlFor="conn-provider">Auth Method</label>
                <select
                  id="conn-provider"
                  value={newConn.provider}
                  onChange={(e) => setNewConn({ ...newConn, provider: e.target.value })}
                >
                  <option value="service_principal">Service Principal</option>
                  <option value="managed_identity">Managed Identity</option>
                  <option value="oauth_delegated" disabled>Delegated OAuth (coming soon)</option>
                </select>
              </div>
            </div>
            {newConn.provider === "service_principal" && (
              <div className="grid-2">
                <div>
                  <label htmlFor="conn-client-id">Client ID (App ID)</label>
                  <input
                    id="conn-client-id"
                    value={newConn.client_id}
                    onChange={(e) => setNewConn({ ...newConn, client_id: e.target.value })}
                    placeholder="e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  />
                </div>
                <div>
                  <label htmlFor="conn-client-secret">Client Secret</label>
                  <input
                    id="conn-client-secret"
                    type="password"
                    value={newConn.client_secret}
                    onChange={(e) => setNewConn({ ...newConn, client_secret: e.target.value })}
                    placeholder="Service principal secret"
                  />
                </div>
              </div>
            )}
            <div className="actions" style={{ marginTop: "8px" }}>
              <button className="secondary" onClick={handleCreateConnection} disabled={creating}>
                {creating ? "Connecting..." : connections.length > 0 ? "Reconnect to Azure" : "Connect to Azure"}
              </button>
            </div>
          </div>

          {/* Run discovery */}
          <div className="card">
            <h3 style={{ margin: "0 0 8px" }}>Run Discovery</h3>
            {connections.length === 0 && <p className="muted">Create a connection first.</p>}
            {connections.length > 0 && (
              <form onSubmit={handleRun}>
                <div className="grid-2">
                  <div>
                    <label htmlFor="connection_id">Connection</label>
                    <select
                      id="connection_id"
                      value={form.connection_id}
                      onChange={(e) => setForm({ ...form, connection_id: e.target.value })}
                      required
                    >
                      {connections.map((c) => (
                        <option key={c.connection_id} value={c.connection_id}>
                          {c.tenant_id} ({c.provider})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="subscription_id">Subscription</label>
                    <select
                      id="subscription_id"
                      value={form.subscription_id}
                      onChange={(e) => setForm({ ...form, subscription_id: e.target.value })}
                    >
                      <option value="">All subscriptions</option>
                      {(selectedConnection?.subscription_ids || []).map((sub) => (
                        <option key={sub} value={sub}>{sub}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label htmlFor="tenant_id">Tenant ID (override)</label>
                  <input
                    id="tenant_id"
                    value={form.tenant_id}
                    onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
                    placeholder="uses connection tenant by default"
                  />
                </div>
                {availableLayers.length > 0 && (
                  <div>
                    <label>Discovery Layers</label>
                    <div className="layer-checkboxes">
                      {availableLayers.map((layer) => (
                        <label
                          key={layer.layer_id}
                          className={`layer-checkbox ${!layer.enabled ? "layer-disabled" : ""}`}
                          title={layer.description}
                        >
                          <input
                            type="checkbox"
                            checked={selectedLayers.includes(layer.layer_id)}
                            disabled={!layer.enabled}
                            onChange={() => handleLayerToggle(layer.layer_id)}
                          />
                          <span>L{layer.layer_number}: {layer.label}</span>
                          {!layer.enabled && <span className="layer-coming-soon">coming soon</span>}
                        </label>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <label htmlFor="message">Message</label>
                  <input
                    id="message"
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                  />
                </div>
                <div className="actions" style={{ marginTop: "4px" }}>
                  <button className="primary" type="submit" disabled={loading || !form.connection_id}>
                    {loading ? "Running..." : "Run Discovery"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Right column: stepper + results */}
        <div className="discovery-results">
          <AgentStepper
            running={loading}
            plan={plan}
            layerPlan={response?.layer_plan || null}
            error={error}
            response={response}
          />

          {error && !loading && !plan && (
            <div className="error" style={{ marginTop: "12px" }}>{error}</div>
          )}

          {/* Category results grid */}
          {categoryResults && !loading && (
            <div className="card">
              <h3 style={{ margin: "0 0 12px" }}>Service Categories</h3>
              <div className="category-grid">
                {Object.entries(categoryResults).map(([cat, result]) => (
                  <div
                    key={cat}
                    className={`category-card category-card-${result.status}`}
                  >
                    <div className="category-card-header">
                      <span className="category-card-name">{cat.replace("_", " ")}</span>
                      <span className={`stepper-badge stepper-badge-${result.status === "completed" ? "done" : result.status === "skipped" ? "skipped" : "error"}`}>
                        {result.status}
                      </span>
                    </div>
                    <div className="category-card-count">
                      {result.resource_count} resource{result.resource_count !== 1 ? "s" : ""}
                    </div>
                    {result.resources && result.resources.length > 0 && (
                      <div className="category-card-resources">
                        {result.resources.slice(0, 3).map((r, i) => (
                          <div key={i} className="category-resource-item">{r.name || r.id}</div>
                        ))}
                        {result.resources.length > 3 && (
                          <div className="category-resource-more">+{result.resources.length - 3} more</div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Layer results */}
          {response?.layer_plan && !loading && (
            <div className="card">
              <h3 style={{ margin: "0 0 12px" }}>Layer Results</h3>
              {response.layer_plan.map((lp) => (
                <div key={lp.layer_id} className="layer-result-group">
                  <div className="layer-result-header">
                    <span className="layer-result-title">L{lp.layer_number}: {lp.label}</span>
                    {lp.auto_resolved && <span className="stepper-auto-tag">auto</span>}
                    <span className={`stepper-badge stepper-badge-${lp.status === "completed" ? "done" : lp.status === "failed" ? "error" : "running"}`}>
                      {lp.status}
                    </span>
                  </div>
                  {lp.steps && lp.steps.length > 0 && (
                    <div className="layer-tool-list">
                      {lp.steps.map((step, i) => (
                        <div key={i} className="layer-tool-item">
                          <span className={`layer-tool-icon ${step.status === "completed" ? "layer-tool-done" : step.status === "failed" ? "layer-tool-fail" : ""}`}>
                            {step.status === "completed" ? "\u2713" : step.status === "failed" ? "\u2717" : "\u2022"}
                          </span>
                          <span className="layer-tool-name">{step.label || step.name}</span>
                          {step.detail?.resource_count != null && (
                            <span className="layer-tool-count">{step.detail.resource_count} resources</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {lp.analysis && (
                    <div className="layer-analysis-stub">
                      Analysis: {lp.analysis.status === "completed" ? "stub" : lp.analysis.status}
                      {lp.analysis.detail?.mode === "stub" && " (AI analysis coming soon)"}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Inventory summary */}
          {response && !loading && response.discovery?.results?.inventory && (
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                <h3 style={{ margin: 0 }}>Discovery Result</h3>
                <div style={{ display: "flex", gap: "8px" }}>
                  {response.discovery?.discovery_id && (
                    <button
                      className="primary"
                      style={{ padding: "6px 12px", fontSize: "12px" }}
                      onClick={() => navigate(`/topology/${response.discovery.discovery_id}`)}
                    >
                      View Topology
                    </button>
                  )}
                  <button
                    className="secondary"
                    style={{ padding: "6px 12px", fontSize: "12px" }}
                    onClick={() => setShowRaw((v) => !v)}
                  >
                    {showRaw ? "Hide Raw" : "Show Raw JSON"}
                  </button>
                </div>
              </div>
              <div className="result-summary">
                <div className="result-row">
                  <span className="result-label">Status</span>
                  <span className={`stepper-badge ${response.discovery?.status === "completed" ? "stepper-badge-done" : "stepper-badge-error"}`}>
                    {response.discovery?.status || "unknown"}
                  </span>
                </div>
                <div className="result-row">
                  <span className="result-label">Total</span>
                  <span>{response.discovery.results.inventory.total_resources} resources</span>
                </div>
                <div className="result-row">
                  <span className="result-label">Summary</span>
                  <span>{response.final_response}</span>
                </div>
                {response.discovery.results.inventory.providers_found?.length > 0 && (
                  <div className="result-row">
                    <span className="result-label">Providers</span>
                    <span>{response.discovery.results.inventory.providers_found.join(", ")}</span>
                  </div>
                )}
              </div>
              {showRaw && (
                <pre className="code-block" aria-label="discovery-output">
{JSON.stringify(response, null, 2)}
                </pre>
              )}
            </div>
          )}

          {!loading && !plan && !error && (
            <div className="empty-state">
              <div className="empty-icon">&#9776;</div>
              <p>Create a connection and run a discovery to see agent workflow progress here.</p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom: Dev Console */}
      <DevConsole logs={logs} onClear={clearLogs} />
    </div>
  );
};

export default Discovery;

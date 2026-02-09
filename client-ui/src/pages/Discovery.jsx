import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const tierOptions = [
  { value: "inventory", label: "Inventory" },
  { value: "cost", label: "Cost" },
  { value: "security", label: "Security" },
];

const Discovery = () => {
  const navigate = useNavigate();
  const [connections, setConnections] = useState([]);
  const [form, setForm] = useState({
    connection_id: "",
    tenant_id: "",
    subscription_id: "",
    tier: "inventory",
    message: "Run discovery for the selected scope.",
  });
  const [plan, setPlan] = useState(null);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newConn, setNewConn] = useState({
    tenant_id: "",
    subscription_ids: "",
    provider: "oauth_delegated",
    rbac_tier: "inventory",
  });

  const selectedConnection = useMemo(
    () => connections.find((c) => c.connection_id === form.connection_id),
    [connections, form.connection_id],
  );

  useEffect(() => {
    api
      .listConnections()
      .then((data) => {
        setConnections(data);
        if (data.length > 0) {
          setForm((prev) => ({
            ...prev,
            connection_id: data[0].connection_id,
            tenant_id: data[0].tenant_id || "",
          }));
        }
      })
      .catch(() => setError("Unable to load connections."));
  }, []);

  const handleRun = async (e) => {
    e.preventDefault();
    setError("");
    setPlan(null);
    setResponse(null);
    setLoading(true);
    try {
      const payload = {
        connection_id: form.connection_id,
        tenant_id: form.tenant_id || undefined,
        subscription_id: form.subscription_id || undefined,
        tier: form.tier,
        message: form.message,
      };
      const data = await api.chat(payload);
      setPlan(data.plan);
      setResponse(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateConnection = async () => {
    setError("");
    setCreating(true);
    try {
      const payload = {
        tenant_id: newConn.tenant_id,
        subscription_ids: newConn.subscription_ids.split(",").map((s) => s.trim()).filter(Boolean),
        provider: newConn.provider,
        rbac_tier: newConn.rbac_tier,
      };
      if (payload.subscription_ids.length === 0) {
        throw new Error("Enter at least one subscription id.");
      }
      const created = await api.createConnection(payload);
      const updated = [...connections, created];
      setConnections(updated);
      setForm((prev) => ({
        ...prev,
        connection_id: created.connection_id,
        tenant_id: created.tenant_id || "",
      }));
      setNewConn({ tenant_id: "", subscription_ids: "", provider: "oauth_delegated", rbac_tier: "inventory" });
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="auth-shell">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <div>
          <h1 className="form-title" style={{ marginBottom: "4px" }}>Discovery Console</h1>
          <p className="muted" style={{ margin: 0 }}>Run discovery via MCP and review the execution plan.</p>
        </div>
        <button className="secondary" onClick={() => navigate("/dashboard")}>
          Back
        </button>
      </div>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h3 style={{ margin: "0 0 8px" }}>Create Connection</h3>
        <div className="grid-2">
          <div>
            <label htmlFor="conn-tenant">Tenant ID</label>
            <input
              id="conn-tenant"
              value={newConn.tenant_id}
              onChange={(e) => setNewConn({ ...newConn, tenant_id: e.target.value })}
              placeholder="tenant-id"
            />
          </div>
          <div>
            <label htmlFor="conn-subs">Subscription IDs (comma separated)</label>
            <input
              id="conn-subs"
              value={newConn.subscription_ids}
              onChange={(e) => setNewConn({ ...newConn, subscription_ids: e.target.value })}
              placeholder="sub-1, sub-2"
            />
          </div>
        </div>
        <div className="grid-2">
          <div>
            <label htmlFor="conn-provider">Provider</label>
            <select
              id="conn-provider"
              value={newConn.provider}
              onChange={(e) => setNewConn({ ...newConn, provider: e.target.value })}
            >
              <option value="oauth_delegated">Delegated OAuth</option>
              <option value="service_principal">Service Principal</option>
              <option value="managed_identity">Managed Identity</option>
            </select>
          </div>
          <div>
            <label htmlFor="conn-tier">RBAC Tier</label>
            <select
              id="conn-tier"
              value={newConn.rbac_tier}
              onChange={(e) => setNewConn({ ...newConn, rbac_tier: e.target.value })}
            >
              {tierOptions.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="actions">
          <button className="secondary" onClick={handleCreateConnection} disabled={creating}>
            {creating ? "Creating..." : "Create Connection"}
          </button>
        </div>
      </div>

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
                {selectedConnection && selectedConnection.rbac_tier && (
                  <p className="muted" style={{ marginTop: "4px" }}>
                    RBAC tier: {selectedConnection.rbac_tier}
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="tier">Discovery tier</label>
                <select id="tier" value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })}>
                  {tierOptions.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid-2">
              <div>
                <label htmlFor="tenant_id">Tenant ID</label>
                <input
                  id="tenant_id"
                  value={form.tenant_id}
                  onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
                  placeholder="tenant-id"
                />
              </div>
              <div>
                <label htmlFor="subscription_id">Subscription ID</label>
                <input
                  id="subscription_id"
                  value={form.subscription_id}
                  onChange={(e) => setForm({ ...form, subscription_id: e.target.value })}
                  placeholder="sub-123"
                />
              </div>
            </div>
            <div>
              <label htmlFor="message">Message</label>
              <input
                id="message"
                value={form.message}
                onChange={(e) => setForm({ ...form, message: e.target.value })}
              />
            </div>
            <div className="actions">
              <button className="primary" type="submit" disabled={loading || !form.connection_id}>
                {loading ? "Running..." : "Run discovery"}
              </button>
            </div>
          </form>
        )}
      </div>

      {response && (
        <div className="card">
          <h3 style={{ margin: "0 0 8px" }}>Execution trace</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            trace_id: {response.trace_id} • correlation_id: {response.correlation_id} • session_id: {response.session_id}
          </p>
          <div className="plan-grid">
            {plan?.map((step) => (
              <div key={step.name} className={`pill ${step.status === "completed" ? "pill-success" : "pill-pending"}`}>
                <div className="pill-title">{step.name}</div>
                <div className="pill-status">{step.status}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: "12px" }}>
            <strong>Summary:</strong> {response.final_response}
          </div>
          <pre className="code-block" aria-label="discovery-output">
{JSON.stringify(response.discovery, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default Discovery;

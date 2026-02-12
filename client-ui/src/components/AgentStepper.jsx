import { useEffect, useState } from "react";

const STAGE_INTERVAL_MS = 700;

function statusIcon(state) {
  if (state === "completed") return "\u2713";
  if (state === "running") return "\u25B6";
  if (state === "failed") return "\u2717";
  if (state === "skipped") return "\u2014";
  return "\u2022";
}

function stateClass(state) {
  if (state === "completed") return "step-completed";
  if (state === "running") return "step-running";
  if (state === "failed") return "step-failed";
  if (state === "skipped") return "step-skipped";
  return "step-pending";
}

/**
 * Default plan used for simulated progress while the request is in flight.
 * Mirrors the fixed stages of the agent workflow.
 */
const DEFAULT_PLAN = [
  { name: "validate", label: "Validate", status: "pending" },
  { name: "inventory", label: "Inventory Scan", status: "pending" },
  { name: "compute", label: "Compute", status: "pending" },
  { name: "storage", label: "Storage", status: "pending" },
  { name: "databases", label: "Databases", status: "pending" },
  { name: "networking", label: "Networking", status: "pending" },
  { name: "app_services", label: "App Services", status: "pending" },
  { name: "aggregate", label: "Aggregate", status: "pending" },
  { name: "persist", label: "Persist", status: "pending" },
];

const AGENT_CATEGORIES = new Set(["compute", "storage", "databases", "networking", "app_services"]);

/**
 * AgentStepper shows the multi-agent discovery pipeline with dynamic stages.
 *
 * Props:
 *  - running: boolean (request in flight)
 *  - plan: array from API response (after completion)
 *  - error: string (if the request failed)
 *  - response: full API response object
 */
const AgentStepper = ({ running, plan, error, response }) => {
  const [simulatedIndex, setSimulatedIndex] = useState(-1);

  const stages = plan && !running ? plan : DEFAULT_PLAN;

  // Animate through stages while request is running
  useEffect(() => {
    if (!running) {
      setSimulatedIndex(-1);
      return;
    }
    setSimulatedIndex(0);
    let idx = 0;
    const interval = setInterval(() => {
      idx += 1;
      if (idx >= stages.length) {
        clearInterval(interval);
      } else {
        setSimulatedIndex(idx);
      }
    }, STAGE_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [running, stages.length]);

  const getStageState = (index) => {
    if (plan && !running) {
      const step = plan[index];
      if (!step) return "pending";
      return step.status || "pending";
    }
    if (error && !running) {
      if (index < simulatedIndex) return "completed";
      if (index === simulatedIndex) return "failed";
      return "pending";
    }
    if (running) {
      if (index < simulatedIndex) return "completed";
      if (index === simulatedIndex) return "running";
      return "pending";
    }
    return "pending";
  };

  const getStageDetail = (index) => {
    if (!plan || running) return null;
    return plan[index]?.detail || null;
  };

  const shouldShow = running || plan || error;
  if (!shouldShow) return null;

  // Check if any stage is a service-category agent
  const hasAgentGroup = stages.some((s) => AGENT_CATEGORIES.has(s.name));

  return (
    <div className="stepper-card">
      <div className="stepper-header">
        <h3 style={{ margin: 0 }}>Agent Workflow</h3>
        {running && <span className="stepper-badge stepper-badge-running">Running</span>}
        {!running && plan && !error && <span className="stepper-badge stepper-badge-done">Complete</span>}
        {!running && error && !plan && <span className="stepper-badge stepper-badge-error">Failed</span>}
      </div>

      <div className="stepper-timeline">
        {stages.map((stage, i) => {
          const state = getStageState(i);
          const detail = getStageDetail(i);
          const isAgent = AGENT_CATEGORIES.has(stage.name);
          const isFirstAgent = isAgent && (i === 0 || !AGENT_CATEGORIES.has(stages[i - 1]?.name));
          const isLastAgent = isAgent && (i === stages.length - 1 || !AGENT_CATEGORIES.has(stages[i + 1]?.name));

          return (
            <div key={stage.name}>
              {/* Group label before first agent */}
              {isFirstAgent && hasAgentGroup && (
                <div className="stepper-agent-group-label">Service Category Agents</div>
              )}
              <div
                className={`stepper-step ${stateClass(state)} ${isAgent ? "stepper-step-agent" : ""} ${isFirstAgent ? "stepper-step-agent-first" : ""} ${isLastAgent ? "stepper-step-agent-last" : ""}`}
              >
                <div className="stepper-connector-wrap">
                  <div className={`stepper-icon ${stateClass(state)}`}>
                    {statusIcon(state)}
                  </div>
                  {i < stages.length - 1 && (
                    <div className={`stepper-line ${state === "completed" ? "stepper-line-done" : ""}`} />
                  )}
                </div>
                <div className="stepper-content">
                  <div className="stepper-label">
                    {stage.label || stage.name}
                    {state === "skipped" && <span className="stepper-skip-tag">skipped</span>}
                  </div>
                  {state === "failed" && error && (
                    <div className="stepper-error-detail">{detail?.error || error}</div>
                  )}
                  {detail && (state === "completed" || state === "failed") && (
                    <div className="stepper-detail">
                      {detail.summary && <span>{detail.summary}</span>}
                      {detail.total_resources != null && <span>resources: {detail.total_resources}</span>}
                      {detail.resource_count != null && <span>found: {detail.resource_count}</span>}
                      {detail.categories_scanned != null && <span>categories: {detail.categories_scanned}</span>}
                      {detail.providers_found?.length > 0 && (
                        <span className="stepper-tool">{detail.providers_found.join(", ")}</span>
                      )}
                      {detail.discovery_id && <span className="stepper-tool">id: {detail.discovery_id.slice(0, 8)}...</span>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Trace IDs after completion */}
      {response && !running && (
        <div className="stepper-trace">
          <span>trace: {response.trace_id?.slice(0, 8)}...</span>
          <span>correlation: {response.correlation_id?.slice(0, 8)}...</span>
          <span>session: {response.session_id?.slice(0, 8)}...</span>
        </div>
      )}
    </div>
  );
};

export default AgentStepper;

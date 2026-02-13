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
 * Only shows generic workflow stages — actual service categories are dynamic
 * and rendered from the API response after completion.
 */
const DEFAULT_PLAN = [
  { name: "validate", label: "Validate", status: "pending" },
  { name: "collect", label: "Collecting Resources", status: "pending" },
  { name: "categorize", label: "Categorizing", status: "pending" },
  { name: "aggregate", label: "Aggregate", status: "pending" },
  { name: "persist", label: "Persist", status: "pending" },
];

/**
 * AgentStepper shows the multi-agent discovery pipeline with dynamic stages.
 *
 * Props:
 *  - running: boolean (request in flight)
 *  - plan: array from API response (after completion)
 *  - layerPlan: array of layer plan entries (when using layered workflow)
 *  - error: string (if the request failed)
 *  - response: full API response object
 */
const AgentStepper = ({ running, plan, layerPlan, error, response }) => {
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

  // Build dynamic category summary from discovery results
  const categories = response?.discovery?.results?.categories;
  const categoryEntries = categories
    ? Object.entries(categories).sort((a, b) => b[1].resource_count - a[1].resource_count)
    : [];

  return (
    <div className="stepper-card">
      <div className="stepper-header">
        <h3 style={{ margin: 0 }}>Agent Workflow</h3>
        {running && <span className="stepper-badge stepper-badge-running">Running</span>}
        {!running && plan && !error && <span className="stepper-badge stepper-badge-done">Complete</span>}
        {!running && error && !plan && <span className="stepper-badge stepper-badge-error">Failed</span>}
      </div>

      {/* Layered workflow rendering */}
      {layerPlan && !running ? (
        <div className="stepper-timeline">
          {layerPlan.map((lp, li) => (
            <div key={lp.layer_id} className="stepper-layer-group">
              <div className="stepper-step">
                <div className="stepper-connector-wrap">
                  <div className={`stepper-icon ${stateClass(lp.status)}`}>
                    {statusIcon(lp.status)}
                  </div>
                  {li < layerPlan.length - 1 && (
                    <div className={`stepper-line ${lp.status === "completed" ? "stepper-line-done" : ""}`} />
                  )}
                </div>
                <div className="stepper-content">
                  <div className="stepper-layer-header">
                    <span className="stepper-label">L{lp.layer_number}: {lp.label}</span>
                    {lp.auto_resolved && <span className="stepper-auto-tag">auto</span>}
                  </div>
                  {/* Sub-steps (tool invocations) */}
                  {lp.steps && lp.steps.length > 0 && (
                    <div className="stepper-sub-steps">
                      {lp.steps.map((step, si) => (
                        <div key={si} className="stepper-sub-step">
                          <span className={`stepper-sub-icon ${stateClass(step.status)}`}>
                            {statusIcon(step.status)}
                          </span>
                          <span className="stepper-sub-label">{step.label || step.name}</span>
                          {step.detail?.resource_count != null && (
                            <span className="stepper-sub-count">{step.detail.resource_count}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Analysis stub */}
                  {lp.analysis && (
                    <div className="stepper-sub-step stepper-sub-analysis">
                      <span className={`stepper-sub-icon ${stateClass(lp.analysis.status)}`}>
                        {statusIcon(lp.analysis.status)}
                      </span>
                      <span className="stepper-sub-label">{lp.analysis.label || "Analysis"}</span>
                      {lp.analysis.detail?.mode === "stub" && (
                        <span className="stepper-sub-stub">stub</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Dynamic service categories from discovered resources */}
          {categoryEntries.length > 0 && (
            <div className="stepper-layer-group">
              <div className="stepper-step">
                <div className="stepper-connector-wrap">
                  <div className="stepper-icon step-completed">{statusIcon("completed")}</div>
                </div>
                <div className="stepper-content">
                  <div className="stepper-layer-header">
                    <span className="stepper-label">Service Categories</span>
                    <span className="stepper-sub-count">{categoryEntries.length}</span>
                  </div>
                  <div className="stepper-sub-steps">
                    {categoryEntries.map(([ns, cat]) => (
                      <div key={ns} className="stepper-sub-step">
                        <span className="stepper-sub-icon step-completed">{statusIcon("completed")}</span>
                        <span className="stepper-sub-label">{cat.label || ns}</span>
                        <span className="stepper-sub-count">{cat.resource_count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Flat workflow rendering (loading animation / legacy) */
        <div className="stepper-timeline">
          {stages.map((stage, i) => {
            const state = getStageState(i);
            const detail = getStageDetail(i);
            return (
              <div key={stage.name}>
                <div className={`stepper-step ${stateClass(state)}`}>
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
                    </div>
                    {state === "failed" && error && (
                      <div className="stepper-error-detail">{detail?.error || error}</div>
                    )}
                    {detail && (state === "completed" || state === "failed") && (
                      <div className="stepper-detail">
                        {detail.summary && <span>{detail.summary}</span>}
                        {detail.total_resources != null && <span>resources: {detail.total_resources}</span>}
                        {detail.resource_count != null && <span>found: {detail.resource_count}</span>}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

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

import { useEffect, useState } from "react";

const STAGES = [
  { key: "validate", label: "Validate", description: "Checking connection scope & RBAC tier" },
  { key: "tier", label: "Discover", description: "Executing tool via MCP boundary" },
  { key: "infer", label: "Analyze", description: "Summarizing discovery results" },
  { key: "persist", label: "Persist", description: "Saving discovery record" },
];

const STAGE_INTERVAL_MS = 900;

function statusIcon(state) {
  if (state === "completed") return "\u2713";
  if (state === "running") return "\u25B6";
  if (state === "failed") return "\u2717";
  return "\u2022";
}

function stateClass(state) {
  if (state === "completed") return "step-completed";
  if (state === "running") return "step-running";
  if (state === "failed") return "step-failed";
  return "step-pending";
}

/**
 * WorkflowStepper shows the 4-stage discovery pipeline with live progress.
 *
 * Props:
 *  - running: boolean (request in flight)
 *  - plan: array from API response (after completion)
 *  - error: string (if the request failed)
 *  - response: full API response object
 */
const WorkflowStepper = ({ running, plan, error, response }) => {
  const [simulatedIndex, setSimulatedIndex] = useState(-1);

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
      if (idx >= STAGES.length) {
        clearInterval(interval);
      } else {
        setSimulatedIndex(idx);
      }
    }, STAGE_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [running]);

  // Determine state of each stage
  const getStageState = (index) => {
    // If we have a real plan from the API, use it
    if (plan && !running) {
      const step = plan[index];
      if (!step) return "pending";
      if (step.status === "completed") return "completed";
      if (step.status === "failed") return "failed";
      return "pending";
    }

    // If there's an error (request failed), mark the simulated stage as failed
    if (error && !running) {
      if (index < simulatedIndex) return "completed";
      if (index === simulatedIndex) return "failed";
      return "pending";
    }

    // While running, show simulated progress
    if (running) {
      if (index < simulatedIndex) return "completed";
      if (index === simulatedIndex) return "running";
      return "pending";
    }

    return "pending";
  };

  const getStageDetail = (index) => {
    if (!plan || running) return null;
    const step = plan[index];
    return step?.detail || null;
  };

  const shouldShow = running || plan || error;
  if (!shouldShow) return null;

  return (
    <div className="stepper-card">
      <div className="stepper-header">
        <h3 style={{ margin: 0 }}>Workflow Progress</h3>
        {running && <span className="stepper-badge stepper-badge-running">Running</span>}
        {!running && plan && !error && <span className="stepper-badge stepper-badge-done">Complete</span>}
        {!running && error && <span className="stepper-badge stepper-badge-error">Failed</span>}
      </div>

      <div className="stepper-timeline">
        {STAGES.map((stage, i) => {
          const state = getStageState(i);
          const detail = getStageDetail(i);
          return (
            <div key={stage.key} className={`stepper-step ${stateClass(state)}`}>
              <div className="stepper-connector-wrap">
                <div className={`stepper-icon ${stateClass(state)}`}>
                  {statusIcon(state)}
                </div>
                {i < STAGES.length - 1 && (
                  <div className={`stepper-line ${state === "completed" ? "stepper-line-done" : ""}`} />
                )}
              </div>
              <div className="stepper-content">
                <div className="stepper-label">{stage.label}</div>
                <div className="stepper-desc">{stage.description}</div>
                {state === "failed" && error && (
                  <div className="stepper-error-detail">{error}</div>
                )}
                {detail && state === "completed" && (
                  <div className="stepper-detail">
                    {detail.summary && <span>{detail.summary}</span>}
                    {detail.counts && (
                      <span className="stepper-counts">
                        {Object.entries(detail.counts).map(([k, v]) => `${k}: ${v}`).join(", ")}
                      </span>
                    )}
                    {detail.tool_id && <span className="stepper-tool">tool: {detail.tool_id}</span>}
                    {detail.discovery_id && <span className="stepper-tool">id: {detail.discovery_id.slice(0, 8)}...</span>}
                  </div>
                )}
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

export default WorkflowStepper;

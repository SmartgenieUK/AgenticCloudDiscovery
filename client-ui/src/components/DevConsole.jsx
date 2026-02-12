import { useEffect, useRef } from "react";

function ts() {
  return new Date().toLocaleTimeString("en-GB", { hour12: false });
}

/**
 * DevConsole renders a scrollable terminal-style log.
 *
 * Props:
 *  - logs: Array<{ time: string, level: "info"|"warn"|"error"|"success", message: string }>
 *  - onClear: function to clear logs
 */
const DevConsole = ({ logs, onClear }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const levelColor = (level) => {
    switch (level) {
      case "error": return "#f87171";
      case "warn": return "#fbbf24";
      case "success": return "#4ade80";
      default: return "#94a3b8";
    }
  };

  const levelPrefix = (level) => {
    switch (level) {
      case "error": return "ERR";
      case "warn": return "WRN";
      case "success": return "OK ";
      default: return "INF";
    }
  };

  return (
    <div className="dev-console">
      <div className="dev-console-header">
        <span className="dev-console-title">Console</span>
        <div className="dev-console-actions">
          <span className="dev-console-count">{logs.length} entries</span>
          {onClear && (
            <button className="dev-console-clear" onClick={onClear}>
              Clear
            </button>
          )}
        </div>
      </div>
      <div className="dev-console-body">
        {logs.length === 0 && (
          <div className="dev-console-line">
            <span style={{ color: "#64748b" }}>[{ts()}] Waiting for activity...</span>
          </div>
        )}
        {logs.map((log, i) => (
          <div key={i} className="dev-console-line">
            <span style={{ color: "#64748b" }}>[{log.time}]</span>{" "}
            <span style={{ color: levelColor(log.level), fontWeight: 600 }}>
              {levelPrefix(log.level)}
            </span>{" "}
            <span style={{ color: log.level === "error" ? "#f87171" : "#e2e8f0" }}>
              {log.message}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export { ts };
export default DevConsole;

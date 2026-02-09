# Observability Specification (Traceability and Cost Visibility)

## Purpose
Provide end-to-end visibility for debugging, governance, and cost control.

## Services
- Application Insights
- Log Analytics Workspace
- Azure Monitor

## Trace Correlation Requirements
Every request must carry:
- session_id (application-level)
- trace_id (distributed tracing)
- span_id (per hop, if using OTel)

## What to Log (Minimum)
### Client UI
- session_id
- request timestamp
- orchestrator latency
- summary of trace received

### Orchestrator
- session_id, trace_id
- model used (gpt-4o, o3-mini/o1)
- plan steps count
- tool chosen
- confidence score (if implemented)
- tool call attempts and outcomes
- final status

### MCP Server
- session_id, trace_id
- tool_id
- policy decision (allow/deny + reason)
- validation outcome
- APIM endpoint called
- status_code, latency_ms

### APIM (Optional in MVP)
- requests, throttling events, auth failures
- correlation via headers

## Redaction
Logs must not include:
- raw credentials
- raw PII payloads by default
Logs may include:
- payload size
- payload hash/fingerprint (optional)
- redacted fields list

## Cost Guardrails (MVP)
- Token budget per session (best-effort visibility)
- Max steps + max tool calls
- Alerts (future phase) for runaway sessions

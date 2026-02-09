# Trust Boundaries and Security

## Trust Boundaries
### Boundary 1 — Client UI (Untrusted)
- Inputs may be malicious or malformed
- No credentials or keys stored
- All calls go to Orchestrator only

### Boundary 2 — Orchestrator (Semi-Trusted Reasoning)
- Performs planning and tool selection
- Must not have direct outbound execution privileges
- Must not hold secrets for target APIs
- Treated as “untrusted for execution” due to probabilistic behavior

### Boundary 3 — MCP Server (Trusted Execution Boundary)
- Deterministic enforcement point
- The only layer allowed to execute outbound calls
- Owns policy, validation, and redaction rules

### Boundary 4 — APIM (Gateway Boundary)
- Controls authentication, throttling, routing
- External dependency boundary to target APIs

## Authentication Strategy
### Azure Mode (Preferred)
- Use Managed Identity for service-to-service authentication where supported
- Key Vault used only when target API requires secrets not supported via MI
- No secrets in code or config repo files

### Local Dev Mode
- Use `.env` in each service directory (gitignored)
- Use mock APIM or test API endpoints
- Must not commit any credentials

## Policy Enforcement (Deterministic)
Policy must be evaluated in MCP Server prior to execution:
- Allowed domains/endpoints
- Allowed methods (GET/POST/PUT/PATCH/DELETE per tool)
- Payload size limits and content controls
- Retry budgets (max retries) and timeouts
- Human approval flag for sensitive tools/actions

## Data Handling Rules
- Do not persist raw request/response bodies by default
- Log redacted summaries only
- Sensitive fields list must be configurable (PII blocklist)
- Store only:
  - tool usage metadata (tool_id, endpoint, status, latency)
  - sanitized payload fingerprints/hashes where needed for caching patterns

## Threats and Mitigations (MVP)
- Prompt injection: isolate execution behind MCP + policy enforcement
- Tool hallucination: require docs-backed confidence threshold and/or approval
- Data exfiltration: domain allowlists, payload filters, no raw persistence
- Credential leakage: MI + Key Vault, no secrets in prompts, no secrets in logs
- Runaway loops: bounded steps + bounded retries + token budgets

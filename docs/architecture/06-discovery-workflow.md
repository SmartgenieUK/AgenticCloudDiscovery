# Discovery Workflow

## Preconditions
- User or application identity is authenticated.
- A Connection exists that binds the identity to a tenantId/subscriptionId scope with required RBAC tier.
- subscriptionId/tenantId provided without a Connection are rejected.

## Discovery Stages
1) **Validate**
   - Input: connection_id, target subscriptionId/tenantId, discovery tier.
   - Checks: Connection status, token freshness, RBAC tier eligibility, policy allowlist, tool availability.
   - Outcome: proceed or fail closed; no external calls yet.
2) **Inventory**
   - MCP calls Azure APIs (via APIM) using the Connection token.
   - Scope-specific APIs based on tier:
     - Inventory: Resource Graph/resource provider list/read.
     - Cost: Cost Management usage/price APIs (requires Cost Management Reader).
     - Security: Defender/Policy/Graph security endpoints (requires Security Reader).
   - Results are streamed back to the Orchestrator for structuring.
3) **Infer**
   - Orchestrator normalizes inventory results, enriches with knowledge base schemas, identifies gaps/misconfigs.
   - No external calls; pure reasoning on returned data and approved docs.
4) **Persist**
   - MCP (or Orchestrator via MCP-owned writers) writes discovery outputs into Cosmos `discoveries` with stage metadata.
   - Session and metrics are updated; correlation_id/trace_id captured.

## Identity and RBAC Handling
- Every MCP tool invocation includes connection_id; tokens are injected server-side, never by the LLM.
- Azure enforces RBAC; denied calls are surfaced as non-retryable auth errors.
- For delegated OAuth, tokens must map to the signed-in user’s RBAC; for enterprise identity, the service principal/managed identity must hold equivalent roles.

## Failure Modes and Guards
- Missing/invalid Connection → block at Validate.
- Insufficient RBAC → fail Inventory stage; do not retry.
- Tool/policy mismatch → blocked by MCP schema/policy validation.
- Expired tokens → request re-authentication/refresh; do not continue discovery with stale credentials.

## Telemetry
- Each stage logs correlation_id, session_id, connection_id, discovery_id, and attempt counters.
- Sensitive fields are redacted; tokens are never logged.***

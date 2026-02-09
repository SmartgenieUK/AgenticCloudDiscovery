# MCP Tools Contract

## Role of MCP
MCP is the single execution boundary for external calls. Orchestrator and UI never call target APIs directly. MCP enforces schema validation, policy checks, RBAC-aligned token usage, and redaction before emitting responses.

## Tool Requirements
- **Inputs (mandatory):**
  - connection_id (references a valid Connection in Cosmos)
  - target scope (tenantId/subscriptionId/resourceGroup as applicable)
  - discovery tier (inventory | cost | security) aligned to RBAC
  - correlation_id / session_id for tracing
- **Identity:**
  - Token injected server-side from the Connection; never supplied by the LLM.
  - Delegated OAuth (MVP) tokens accepted; enterprise flows may supply application tokens, but the tool interface stays unchanged.
- **Policy Enforcement:**
  - Allowed domains/methods checked against policies container.
  - Payload size and schema validated before dispatch.
  - Deny on unknown tools, disallowed methods, or missing Connection.
- **Execution:**
  - All outbound HTTP goes through APIM.
  - Retries follow policy-defined budgets; auth/403/401 are non-retryable.
  - RBAC denials are returned to the Orchestrator for user-facing messaging.
- **Outputs:**
  - Structured JSON with inventory results, cost aggregates, or security findings depending on tier.
  - No tokens or secrets in outputs. Include minimal metadata: discovery_id, stage, counts, timestamps.

## Tool Categories (MVP)
- Inventory tools: enumerate resources/providers; read-only.
- Cost tools: retrieve usage/cost data for authorized scopes.
- Security tools: pull policy/compliance/defender posture for authorized scopes.

## Validation Flow
1) Orchestrator selects tool and passes connection_id + scope + tier.
2) MCP validates schema/policy; loads Connection and token.
3) MCP calls Azure APIs via APIM with the token.
4) MCP returns structured results; Orchestrator proceeds to infer/persist.

## Cold-Start Tool Discovery
- Tool definitions may be drafted from AI Search + Document Intelligence.
- Draft tools remain pending until approved; pending tools cannot execute.

## Logging and Redaction
- Log correlation_id, session_id, connection_id, tool_id, stage, and status.
- Do not log tokens, PII, or payloads containing secrets. Only store sanitized outputs in Cosmos.***

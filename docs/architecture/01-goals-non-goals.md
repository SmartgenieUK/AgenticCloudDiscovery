# Goals and Non-Goals

## Goals (MVP)
### G1 — Governed Execution Boundary
All outbound execution occurs via MCP Server with deterministic enforcement:
- Allowed domains / endpoints
- Allowed HTTP methods
- Payload/schema validation
- Retry budgets and error class rules (enforced via policy)

### G2 — Practical Autonomy
The system can operate without hard-coded workflows by:
- Discovering API documentation in AI Search
- Extracting missing details from docs using Document Intelligence (when required)
- Proposing tool definitions and executing approved tools

### G3 — Bounded Self-Healing
For selected error classes (e.g., 400 validation errors), the Orchestrator can:
- Interpret error response
- Correct payload formatting/types
- Retry within policy-defined limits

### G4 — End-to-End Observability
Every request is traceable across all hops with:
- session_id
- trace_id
- tool_id
- agent_step / attempt numbers
- latency and status codes
- (best effort) token usage and model routing

### G5 — Enterprise-Safe Defaults
- No secrets in code
- Prefer Managed Identity in Azure
- No default persistence of raw PII payloads
- Controlled tool publication (human approval toggle)

## Non-Goals (MVP)
### NG1 — Fully Automated Tool Publishing Without Approval
Auto-generation is permitted, but publication must be gated (configurable approval step).

### NG2 — Multi-Tenant Isolation / Billing
MVP is single-tenant. Multi-tenant RBAC/billing is a later phase.

### NG3 — Complex UI/UX
UI is a functional console (chat + trace), not a polished product experience.

### NG4 — Broad Connector Catalogue
MVP targets 1–2 APIs to prove the architecture, not a marketplace of integrations.

### NG5 — Perfect Prompting
The goal is platform control and determinism, not prompt-only compliance.

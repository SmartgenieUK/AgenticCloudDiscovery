# AGENTS.md

## Purpose
Guidelines for any agentic or automated code generation operating on this repository. Enforces identity-first discovery, safe execution boundaries, and correct usage of platform components.

## Scope
- Applies to all agents/codegen that read, plan, or propose changes in `AgenticCloudDiscovery`.
- Complements `docs/architecture/*`; if conflicts arise, architecture docs win.

## Identity and Access
- subscriptionId / tenantId are identifiers only; they are never credentials.
- Discovery requires an authorized Connection with a valid token and RBAC on the target scope.
- Do not store or log tokens, refresh tokens, or secrets. Do not echo them in prompts.

## Execution Boundaries
- All external API calls must go through MCP tools and APIM; no direct HTTP from agents.
- Do not add new runtime dependencies or frameworks without explicit human approval.
- Do not modify application code unless explicitly requested; default to documentation-only changes when uncertain.

## Data Handling
- Cosmos DB is the system of record. Respect container responsibilities documented in `docs/architecture/02-data-model-cosmos.md`.
- Redact PII and secrets in logs and outputs. Use correlation_id/session_id for tracing.

## Auth Models
- MVP: delegated OAuth tokens bound to a Connection; Azure RBAC enforces scope.
- Enterprise: service principal or managed identity; same Connection concept, different token source.

## Discovery Workflow (enforced)
- Validate (Connection, RBAC, policy) → Inventory (MCP tools) → Infer (no outbound calls) → Persist (Cosmos).
- Fail closed on missing Connection, RBAC denial, or policy violation.

## Safe Defaults for Agents
- When unsure about access, ask for a Connection id and discovery tier; never proceed with identifiers alone.
- Avoid generating code that bypasses MCP or APIM.
- Keep edits minimal and incremental; prefer updating docs or configs over code changes unless instructed.

## References
- `docs/architecture/00-overview.md`
- `docs/architecture/01-identity-auth.md`
- `docs/architecture/03-discovery-workflow.md`
- `docs/architecture/04-mcp-tools-contract.md`

# Identity and Authorization Model

## Intent
Discovery is identity-first. subscriptionId and tenantId identify targets but never grant access. Every discovery operation requires an authenticated Connection that supplies a valid token and aligns with Azure RBAC.

## Principles
- subscriptionId / tenantId are identifiers only; they do not imply access.
- Authorization is explicit per Connection; no implicit trust from user input.
- Tokens are scoped and time-bound; refresh is handled out-of-band of the LLM.
- Azure RBAC is the source of truth for what discovery operations may enumerate.
- All external calls are executed via MCP tools that receive the appropriate token.

## Connections (Authorized Discovery Scopes)
- A Connection binds: user (or app identity) ↔ tenantId ↔ subscriptionId(s)/scope ↔ token + metadata (provider, expiry).
- Connections are stored in Cosmos DB; they are required inputs to discovery tools.
- Connections include an authorization level indicating allowed discovery tiers (e.g., inventory-only vs cost vs security posture), driven by RBAC.

## Authentication Modes
- **MVP (Delegated OAuth):** User signs in; UI obtains delegated token; MCP uses that token per Connection. Requires user RBAC on the target scopes.
- **Enterprise (Application Identity):** Service principal or managed identity with consented scopes; MCP uses application tokens; still constrained by RBAC. No code changes required—only token acquisition changes.

## RBAC Requirements by Discovery Tier
- Inventory (resource graph/resource provider read): Reader or higher.
- Cost (Consumption/Usage APIs): Cost Management Reader (or equivalent) on the subscription/resource group.
- Security (Defender/Policy posture): Security Reader or higher on the scope.
- MCP tools must fail closed if RBAC denies a call; Orchestrator must surface the denial and avoid retries for auth errors.

## Token Handling
- Delegated tokens are acquired by the UI, stored server-side only in secure session context, and passed to MCP tools per Connection.
- Tokens are never logged; correlation IDs are used for tracing without PII.
- Refresh tokens (when used) are stored securely and not exposed to the LLM or MCP logs.

## Input Validation Rules
- Reject discovery requests that provide only subscriptionId/tenantId without a bound Connection.
- Require a Connection identifier on every discovery tool invocation.
- Validate that the Connection scope matches the requested discovery scope before tool execution.

## Enforcement Points
- UI: enforces interactive sign-in; no unauthenticated discovery.
- Orchestrator: requires Connection id, validates scope, and passes only non-secret identifiers to the LLM.
- MCP: validates schema, policy, Connection binding, and executes with provided token through APIM.
- Azure: enforces RBAC on every API call.***

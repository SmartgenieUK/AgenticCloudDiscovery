# Cosmos Data Model

Cosmos DB is the system of record for identity, policy, tool metadata, sessions, and discovery outputs. Containers are partitioned for isolation and throughput; all writes and reads are performed by services (never the LLM directly).

## Containers and Responsibilities
- **users** (pk: `/user_id`): authentication profiles; stores name, email, auth_provider, provider_subject_id, password_hash (email auth), created_at/updated_at, last_login_at. No secrets beyond hashes.
- **connections** (pk: `/connection_id`): authorized discovery scopes. Fields: user_id or app_id, tenant_id, subscription_ids or scope, provider (`oauth_delegated`, `service_principal`, `managed_identity`), token metadata (expires_at, provider_refresh_handle if applicable), rbac_tier (`inventory`, `cost`, `security`), created_at/updated_at, status (`active`, `expired`, `revoked`).
- **policies** (pk: `/policy_id`): allow/deny domains, methods, max payload, retry limits, approval flags; used by MCP for enforcement.
- **tools** (pk: `/tool_id`): tool schemas, descriptions, allowed domains/methods, status (`pending|approved|disabled`), provenance (manual/generated), source_docs.
- **sessions** (pk: `/session_id`): conversation metadata, last_intent_summary (redacted), model_routing_summary, metrics (steps_count, tool_calls_count, retry_count), created_at/updated_at.
- **discoveries** (pk: `/discovery_id`): discovery job metadata and outputs. Fields: connection_id, target (tenantId/subscriptionId), stage status (validate/inventory/infer/persist), findings (resource summaries, inferred gaps), timestamps, errors (redacted), correlation_id.

## Identity and Token Storage Constraints
- Tokens are stored only as opaque provider handles or short-lived access tokens; never expose to LLM or logs.
- Connection records must not contain raw refresh tokens; use provider-secured references where possible.
- PII and secrets must be redacted before persistence outside the users or connections containers.

## Access Patterns
- Orchestrator reads users/sessions/tools/policies to plan; writes sessions and discovery metadata.
- MCP reads tools/policies/connections; executes tools with the provided token; writes discoveries.
- UI initiates user records and connections via authenticated flows; never accesses Cosmos directly.

## Retention and Integrity
- All containers carry created_at and updated_at for auditability.
- discovery outputs are immutable once persisted; updates create new versions or append-only stages.
- Session and discovery records include correlation_id and trace_id for cross-service observability.***

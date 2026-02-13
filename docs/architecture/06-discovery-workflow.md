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

## Layer-Based Discovery Model

Discovery is organised into 8 concern-based layers. Each layer looks at the subscription from a different angle and runs a two-phase pipeline: **Collection** (MCP tool calls) then **Analysis** (AI reasoning — currently stubbed).

| # | Layer ID | Label | Dependencies | Collection Tools | Enabled |
|---|----------|-------|-------------|-----------------|---------|
| 1 | `inventory` | Inventory | none | `rg_inventory_discovery` | Yes |
| 2 | `topology` | Topology | inventory | `rg_topology_discovery` | Yes |
| 3 | `identity_access` | Identity & Access | inventory | `rg_identity_discovery`, `rg_policy_discovery` | Yes |
| 4 | `data_flow` | Data Flow | inventory, topology | (pending) | No |
| 5 | `dependencies` | Dependencies | inventory, topology | (pending) | No |
| 6 | `governance` | Governance | inventory | (pending) | No |
| 7 | `ha_dr` | HA & DR | inventory, topology | (pending) | No |
| 8 | `operations_cost` | Operations & Cost | inventory | cost_discovery | No |

### Dependency Resolution

When a user selects layers to run, the system automatically resolves and prepends any missing dependencies. For example, requesting only `topology` will auto-resolve `inventory` as a prerequisite. The resolution is topological — layers always execute in ascending layer_number order.

### Resource Graph Query Engine

Layers 1-3 use Azure Resource Graph as the primary extraction engine instead of individual ARM list API calls. This reduces 16 sequential HTTP GET calls to 4 POST queries with KQL.

**Endpoint:** `POST https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01`

**KQL Templates per tool:**

| Tool | Table | KQL Summary |
|------|-------|-------------|
| `rg_inventory_discovery` | `resources` | Full resource inventory with all projected fields |
| `rg_topology_discovery` | `resources` | Filtered to 7 network resource types (NICs, NSGs, PIPs, VNets, route tables, private endpoints, load balancers) |
| `rg_identity_discovery` | `authorizationresources` | Role assignments and role definitions |
| `rg_policy_discovery` | `policyresources` | Policy assignments |

**Pagination:** Resource Graph returns max 1000 rows per page. The executor loops on `$skipToken` until all results are collected (capped at 100 pages for safety).

**Throttle resilience:** The executor parses `x-ms-user-quota-remaining` and `x-ms-user-quota-resets-after` response headers. If remaining quota < 2, it proactively sleeps before the next request. On HTTP 429, it respects the `Retry-After` header.

**Subscription batching:** Resource Graph accepts up to 1000 subscription IDs per query in the request body. The `subscription_ids` array from the connection is passed directly.

**Legacy ARM tools preserved:** The original 16 individual ARM tools remain in the tool registry with `status: "approved"`. The old category-based workflow (`POST /chat` without `layers`) still uses them unchanged.

### Layer Pipeline

Each layer executes:
1. **Collection phase** — sequentially runs each tool in the layer's `collection_tool_ids` via MCP. All layers use the same execution path (no special-case handling).
2. **Analysis phase** — currently a stub returning `{status: "stub"}`. Future: LLM-based reasoning over collected data to produce insights and recommendations.

### Results Structure

When the layered workflow is used, the discovery results include:
```json
{
  "results": {
    "layers": {
      "inventory": { "tools": {...}, "analysis": {...} },
      "topology": { "tools": {...}, "analysis": {...} },
      "identity_access": { "tools": {...}, "analysis": {...} }
    },
    "inventory": {...},    // backward-compatible flat inventory
    "categories": {...}    // backward-compatible category results
  }
}
```

### Backward Compatibility

- When neither `layers` nor `categories` is specified in the request, the original agent-based workflow runs unchanged (uses legacy ARM tools).
- When `layers` is specified, both the new `results.layers` and legacy `results.inventory`/`results.categories` keys are populated for backward compatibility. Category results are derived by splitting Resource Graph inventory results by resource type prefix.
- The `ChatResponse` includes both a flat `plan` (for existing UI) and a hierarchical `layer_plan` (for layered UI).

### API Endpoints

- `GET /layers` — returns all 8 layers with metadata (layer_id, label, description, depends_on, enabled)
- `POST /chat` with `layers: ["inventory", "topology"]` — runs layered workflow
- `POST /discoveries` with `layers: ["inventory"]` — runs layered workflow via discovery endpoint

## Telemetry
- Each stage logs correlation_id, session_id, connection_id, discovery_id, and attempt counters.
- Sensitive fields are redacted; tokens are never logged.

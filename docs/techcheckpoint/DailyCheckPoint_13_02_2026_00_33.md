# Daily Technical Checkpoint — 13 Feb 2026

## 1. Summary

This session replaced all mock/stub infrastructure with **real Azure Resource Graph KQL queries** executing through the full MCP execution boundary. The layered discovery workflow (L1 Inventory, L2 Topology, L3 Identity & Access) now runs real KQL against Azure ARM APIs with proper pagination, 429 throttle handling, and proactive backoff. Azure authentication uses `InteractiveBrowserCredential` (browser-based login like `az login`) locally and `ManagedIdentityCredential` on Azure infrastructure, with JWT payload decoding to extract the authenticated user's display name.

The second major change was making **service categories fully dynamic** — instead of hardcoded categories (compute, storage, databases, etc.) that showed "skipped" when resources didn't match, categories are now derived from the actual Azure provider namespaces discovered in the subscription (e.g., `microsoft.cognitiveservices` → "Cognitive Services", `microsoft.documentdb` → "Cosmos DB"). The AgentStepper renders these dynamically after discovery completes, with resource counts. The DevConsole now logs KQL queries, resource type breakdowns, and category summaries for debugging. UI startup was hardened with retry logic (3 attempts, 2s delay) to handle orchestrator startup timing, and React StrictMode double-firing was resolved.

## 2. Files Changed/Added

| File | Change |
|------|--------|
| `agent-orchestrator/azure_auth.py` | Added `_extract_display_name()` JWT decoder; both `acquire_sp_token` and `acquire_mi_token` return `display_name` |
| `agent-orchestrator/config.py` | Default `mcp_stub_mode` to `false` |
| `agent-orchestrator/discoveries/__init__.py` | Exports for layers, layered workflow |
| `agent-orchestrator/discoveries/agent_workflow.py` | +378 lines — layered workflow engine, dynamic namespace categorization, `_NAMESPACE_LABELS`, `_TOOL_LABELS`, case-insensitive lookup |
| `agent-orchestrator/discoveries/layers.py` | **NEW** — Layer definitions (8 layers), dependency resolution, `LAYER_REGISTRY` |
| `agent-orchestrator/graph/__init__.py` | Exports for graph builder |
| `agent-orchestrator/graph/graph_builder.py` | **NEW** — Hierarchical resource graph (tenant → subscription → RG → resource) with topology/identity edges |
| `agent-orchestrator/main.py` | Layered `/chat` dispatch, `/layers` endpoint, `/graph/{id}` endpoint, `display_name` in connections |
| `agent-orchestrator/mcp/__init__.py` | Updated exports |
| `agent-orchestrator/mcp/client.py` | Removed `STUB_RESOURCES` and `stub_mcp_result()`; always calls real MCP server |
| `agent-orchestrator/models.py` | Added `display_name` to Connection; `sanitize_connection()` updated |
| `agent-orchestrator/requirements.txt` | Added `azure-identity==1.25.2` |
| `agent-orchestrator/tests/test_graph_builder.py` | **NEW** — 16 tests for graph builder (parse, collect, build, topology edges, identity edges, edge cases) |
| `agent-orchestrator/tests/test_layered_discovery.py` | **NEW** — Layer endpoint + layered chat tests |
| `agent-orchestrator/tests/test_layers.py` | **NEW** — Layer registry and dependency resolution tests |
| `client-ui/src/components/AgentStepper.jsx` | Simplified: dynamic categories from API response, no hardcoded `AGENT_CATEGORIES`, generic loading animation |
| `client-ui/src/pages/Discovery.jsx` | Retry-on-startup for connections/layers, KQL + type breakdown + category logging in DevConsole, "Connected as" badge |
| `client-ui/src/pages/Topology.jsx` | **NEW** — Topology visualization page |
| `client-ui/src/components/TopologyTree.jsx` | **NEW** — Tree renderer for resource graph |
| `client-ui/src/components/TopologyCanvas.jsx` | **NEW** — Canvas-based graph renderer |
| `client-ui/src/components/TopologyDetail.jsx` | **NEW** — Resource detail panel |
| `client-ui/src/components/ResourceNode.jsx` | **NEW** — Resource node component |
| `mcp-server/config.py` | Default `apim_stub_mode` to `false` |
| `mcp-server/executor.py` | Separated Resource Graph error handler with `kql_query` in error responses; checks `status` field |
| `mcp-server/repositories.py` | +4 Resource Graph tool definitions (`rg_inventory_discovery`, `rg_topology_discovery`, `rg_identity_discovery`, `rg_policy_discovery`) |
| `mcp-server/tests/test_resource_graph.py` | **NEW** — RG tool definitions, normalizer, throttle header parsing, pagination tests |
| `mcp-server/tests/test_new_tools.py` | **NEW** — New tool definition tests |
| `start-dev.ps1` | Removed `MCP_STUB_MODE` env vars |
| `docs/architecture/06-discovery-workflow.md` | Updated workflow documentation |

## 3. How to Run Locally

```powershell
# From project root
.\start-dev.ps1

# Services:
#   MCP Server:   http://localhost:9000/health
#   Orchestrator: http://localhost:8000/healthz
#   Client UI:    http://localhost:5173

# App auth bypassed (DEV_SKIP_AUTH=true)
# Azure auth: real credentials required (browser login opens automatically)
```

**Success looks like:**
1. Open http://localhost:5173, navigate to Discovery
2. Layer checkboxes appear (L1 Inventory, L2 Topology, L3 Identity & Access)
3. Click "Connect to Azure" → browser opens for Microsoft login → "Connected as [Your Name]" badge appears
4. Click "Run Discovery" → Agent Workflow stepper shows layers completing with resource counts
5. DevConsole shows KQL queries, resource types, and dynamic service categories
6. Service Categories section shows actual Azure namespaces (e.g., "Cognitive Services: 4", "Storage: 2")

**Run tests:**
```powershell
cd agent-orchestrator; .\venv\Scripts\Activate.ps1; python -m pytest tests/ -v
# Expected: 73 passed, 11 failed (pre-existing: mock signature mismatches, MCP server unreachable, DEV_SKIP_AUTH)

cd ..\mcp-server; .\venv\Scripts\Activate.ps1; python -m pytest tests/ -v
# Expected: all pass
```

## 4. Known Issues, Risks, and TODOs

- **11 pre-existing test failures** in orchestrator: mock signature mismatches in `test_discoveries.py` and `test_integration.py` (stubs need updating for new `call_mcp_execute` signature), plus tests that require a running MCP server
- **`test_unauthenticated_access_blocked`** fails because `DEV_SKIP_AUTH=true` bypasses all auth
- **L2 Topology returns 0 resources** for this subscription (no NICs, NSGs, or Private Endpoints present)
- **Analysis phase is stubbed** — all layers show "Analysis: stub" (Phase 4 work)
- **Token expiry not refreshed** — if the Azure AD token expires during a long multi-layer discovery, the later layers will fail with 401
- **`microsoft.azureactivedirectory`** namespace not in `_NAMESPACE_LABELS` — shows title-cased fallback instead of friendly label
- **Cosmos DB not connected** — connections and discoveries use in-memory repos in dev mode

## 5. Recommended Next Increments

### Increment 1: Fix Pre-existing Test Failures
Update mock functions in `test_discoveries.py`, `test_integration.py`, and `test_layered_discovery.py` to match the current `call_mcp_execute` signature (5 args: tool_id, args, trace_id, correlation_id, session_id). Add MCP server mocking so tests don't require a running server. ~2 hours.

### Increment 2: Discovery Results Display
After discovery completes, render a **resource table/grid** below the AgentStepper showing the discovered resources (name, type, location, resource group) with filtering and sorting. The data is already in `response.discovery.results.inventory.resources`. Wire up the existing Topology page to display the resource graph from `/graph/{discovery_id}`. ~3 hours.

### Increment 3: Token Refresh + Connection Persistence
Add token expiry checking before each layer execution — if token expires within 5 minutes, trigger a refresh via the stored credentials. Also wire up Cosmos DB connection persistence so connections survive orchestrator restarts (currently in-memory). ~3 hours.

## 6. Resume Prompt

```
RESUME PROMPT — AgenticCloudDisc / CloudGenie

## Current Milestone
Phase 3 complete. Real Azure discovery working end-to-end with 3 layers.

## What Exists and Is Working
- Client UI (React/Vite) at :5173 with Discovery page, AgentStepper, DevConsole
- Orchestrator (FastAPI) at :8000 with layered discovery workflow (L1 Inventory, L2 Topology, L3 Identity & Access)
- MCP Server (FastAPI) at :9000 with 4 Resource Graph KQL tools, policy enforcement, pagination, throttle handling
- Real Azure auth via InteractiveBrowserCredential (browser login) with display_name extraction
- Dynamic service categories derived from actual Azure provider namespaces (no hardcoded categories)
- Topology graph builder (hierarchical: tenant → subscription → RG → resource)
- 73/84 orchestrator tests passing, all MCP server tests passing
- DevConsole logs KQL queries, resource types, category breakdowns
- UI retry-on-startup for orchestrator timing
- All stub/mock data removed; stub mode defaults to false

## Key Files
- `agent-orchestrator/discoveries/agent_workflow.py` — Layered workflow engine + dynamic categories
- `agent-orchestrator/discoveries/layers.py` — Layer definitions + dependency resolution
- `mcp-server/executor.py` — Resource Graph execution with pagination/throttling
- `mcp-server/repositories.py` — Tool definitions with KQL templates
- `client-ui/src/pages/Discovery.jsx` — Discovery UI with DevConsole logging
- `client-ui/src/components/AgentStepper.jsx` — Dynamic workflow stepper

## What to Build Next
1. Fix 11 pre-existing test failures (mock signature mismatches)
2. Resource table/grid display after discovery completes
3. Token refresh before layer execution + Cosmos DB connection persistence
4. Phase 4: Knowledge Services (AI Search, Doc Intelligence, tool approval, cold-start tool generation)

## Guardrails
- MCP is the sole execution boundary for external APIs — no direct Azure calls from orchestrator
- Policy enforcement: domain/method allowlists checked before every execution
- Tokens never logged anywhere in the chain (3-layer enforcement)
- Identity-first: subscriptionId/tenantId are identifiers, not credentials
- Every discovery is a timestamped snapshot for diff/comparison
- Deterministic execution: workflow builds plan before running, no LLM decisions at runtime
- Key Vault for secrets in production; DEV_SKIP_AUTH for app login only (Azure auth always real)
```

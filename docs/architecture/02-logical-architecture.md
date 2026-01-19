# Logical Architecture

## Logical Flow (Request Lifecycle)
1. User submits query in Client UI.
2. UI calls Orchestrator `/chat` with a new `session_id` (or receives one from Orchestrator).
3. Orchestrator:
   - Performs intent extraction
   - Routes model usage (GPT-4o vs o3-mini/o1)
   - Creates a plan (bounded steps)
4. Orchestrator requests tool list from MCP Server (tool registry).
5. If a required tool is missing:
   - Orchestrator queries AI Search for documentation
   - Extracts specifics (endpoint, headers, payload schema)
   - Produces a draft tool definition
   - Publishes as “pending approval” (or requests approval depending on config)
6. Orchestrator selects a tool and sends an execution request to MCP:
   - Includes session_id, tool_id, arguments, trace metadata
7. MCP Server enforces:
   - Policy checks (domain allowlist, method allowlist, max payload, etc.)
   - Schema validation (pydantic)
   - Redaction rules for logs
8. MCP Server calls APIM endpoint (not direct target API).
9. APIM handles:
   - Authentication to target API
   - Throttling/rate limiting
   - Routing and transforms if required
10. Response returns to MCP → Orchestrator.
11. Orchestrator:
   - Optionally self-heals and retries within policy
   - Synthesizes final response to UI
   - Returns trace summary for display
12. Telemetry is emitted at every hop (correlated).

## Component Responsibilities
### Client UI
- Collect query and display results + trace
- No secrets, no direct calls to MCP or target APIs

### Orchestrator Service
- Reasoning and planning
- Tool selection and execution coordination
- Knowledge lookup (AI Search)
- Confidence gating and retry logic
- Never stores secrets
- Never calls external APIs directly (only via MCP)

### MCP Server
- Tool registry and execution boundary
- Policy enforcement (deterministic)
- Validation (schema, payload size, allowed domain/method)
- Structured logging, redaction
- Calls out via APIM only

### AI Search + Document Intelligence
- Documentation ingestion and retrieval
- Vector search for endpoint discovery and schema hints
- Used when tool metadata is incomplete or missing

### Cosmos DB
- Policies (versioned)
- Tool registry records (approved/pending)
- Session state and execution summaries (sanitized)
- Successful interaction patterns (sanitized)

## Required Correlation Fields
- session_id: stable per user conversation/session
- trace_id: distributed tracing identifier
- tool_id: resolved tool execution identifier
- attempt: retry attempt number
- agent_step: step number in plan

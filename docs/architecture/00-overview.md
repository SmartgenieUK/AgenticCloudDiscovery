# Cloud Agentic Discovery (ACD) Architecture Overview

## Purpose
Cloud Agentic Discovery delivers governed, authenticated discovery of Azure resources through an agentic execution pattern. Discovery is identity-first: subscriptionId and tenantId are identifiers, never credentials. Authenticated Connections, RBAC validation, and MCP-enforced execution prevent unauthorised access while enabling flexible, tool-driven exploration.

## MVP Scope (Delegated OAuth)
- Accept discovery requests via a minimal web UI.
- Authenticate users with delegated OAuth and bind tokens to explicit Connections.
- Plan and execute discovery through the Orchestrator, using only MCP tools for external calls.
- Persist users, Connections, sessions, policies, tools, and discovery results in Cosmos DB (system of record).
- Emit correlated telemetry (session_id, trace_id, correlation_id) across services.

## Core Principles
- **Identity first:** Discovery requires authenticated access; identifiers alone are insufficient.
- **Deterministic execution:** The LLM proposes; policy + MCP decide and execute.
- **Single egress path:** All external API calls flow through MCP tools and APIM.
- **Separation of concerns:** Reasoning (Orchestrator), execution (MCP), storage (Cosmos), telemetry (App Insights/Log Analytics).
- **Least privilege:** Delegated scopes (MVP) and application identities (enterprise) respect Azure RBAC.

## High-Level Components
- Client UI: session entry; collects auth grant for delegated OAuth; drives discovery flows.
- Orchestrator API: planning, tool selection, confidence gating, session management; no direct external calls.
- MCP Server: execution boundary, schema/policy validation, redaction, outbound enforcement via APIM.
- Knowledge Services: AI Search + Document Intelligence for tool/schema discovery.
- Data/State (Cosmos DB): users, Connections, policies, tools, sessions, discovery results.
- Observability: Application Insights + Log Analytics with correlated IDs.

## Identity and Access Posture
- subscriptionId / tenantId are discovery targets only after an authorized Connection exists.
- MVP: delegated OAuth user tokens; enterprise: service principal or managed identity with RBAC.
- Azure enforces RBAC during MCP tool execution; MCP carries the token bound to the Connection.

## Execution Boundary
- MCP is the sole path for external API calls; Orchestrator and UI never call target APIs.
- APIM fronts outbound calls for auth, throttling, and routing.
- Tool registry and policy gating prevent unapproved methods/domains.

## Azure Services (MVP)
- Azure Container Apps (MCP Server, Orchestrator, optional UI backend)
- Azure OpenAI (GPT-4o + o3-mini/o1)
- Azure API Management
- Azure AI Search and Azure AI Document Intelligence
- Azure Cosmos DB (NoSQL)
- Azure Key Vault (secrets, prefer Managed Identity)
- Application Insights + Log Analytics

## Repository Layout (Target)
- infra/                 Infrastructure as Code (Bicep preferred)
- mcp-server/            MCP execution boundary
- agent-orchestrator/    Orchestrator API + agent loop + knowledge lookup
- client-ui/             Minimal web UI (trace-first)
- shared/                Shared telemetry + models
- docs/architecture/     Architecture contract (source of truth)
- docs/prompts/          Start/End prompts for session continuity

## Definition of Done (MVP)
- UI ↔ Orchestrator ↔ MCP ↔ APIM ↔ Target API flow works with authenticated Connections.
- Policy enforcement blocks disallowed methods/domains; RBAC is honored by Azure.
- Orchestrator performs bounded retries and self-healing on payload errors.
- Telemetry shows correlated trace across services.
- Cold-start tool discovery works with approval gating for new tools.

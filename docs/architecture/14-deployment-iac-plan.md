# Deployment and IaC Plan (Azure MVP)

## Target Runtime
Azure Container Apps hosts:
- mcp-server (internal + secured ingress as needed)
- agent-orchestrator (public/internal depending on MVP)
- client-ui (optional static hosting or ACA)

## Identity
- Managed Identity for each Container App
- RBAC assignments:
  - Orchestrator → AI Search query
  - Orchestrator → Document Intelligence (if used at runtime)
  - MCP Server → APIM invoke
  - Services → App Insights write (handled by platform)
  - Services → Key Vault read only if required

## Key Vault
- Store secrets only if target APIs require static keys
- Never store secrets in code or committed files

## APIM
- Outbound API gateway
- Handles authentication, throttling, and routing
- Policy templates should be part of infra repo when feasible

## Observability
- App Insights enabled for each Container App
- Logs routed to Log Analytics
- Standard correlation headers passed across calls

## Environments
- local: `.env` + mock APIM or test API
- dev: Azure resources deployed via Bicep
- prod (future): same pattern, tightened policies

## Outputs Required from IaC
- Orchestrator endpoint URL
- MCP endpoint URL (internal/public)
- AI Search endpoint/index name
- Cosmos DB endpoint/database/container names
- App Insights instrumentation settings (if required)
- APIM gateway URL

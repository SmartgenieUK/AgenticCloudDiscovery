# AgenticCloudDiscovery
Agentic cloud discovery solution

## Overview
This repository delivers a governed, observable agentic platform on Azure that can interpret user intent, discover how to call APIs, and execute those calls through a controlled execution boundary. The system avoids hard-coded workflows and is designed to scale in capability without becoming a security or operations liability.

## MVP Statement
Build a working MVP that:
- Accepts a user query via a minimal web UI
- Uses an Orchestrator (LLM) to plan and choose tools
- Executes tools only through an MCP Server (execution boundary)
- Enforces deterministic policy and validation outside the LLM
- Emits end-to-end telemetry with correlation IDs
- Supports cold-start tool discovery from ingested API documentation
- Demonstrates bounded self-healing retries for controlled error classes

## Core Design Principle
**The LLM proposes actions. The platform decides what is allowed and executes deterministically.**

## High-Level Components
- **Client UI (Web)**: sends requests, shows answer + trace
- **Orchestrator API**: reasoning, planning, tool selection, confidence gating
- **MCP Server**: tool registry + policy enforcement + validation + execution
- **APIM**: API gateway for outbound calls (auth, throttling, routing)
- **Knowledge Services**: Document Intelligence + AI Search for API docs and schemas
- **State/Memory**: Cosmos DB for policies, tool registry, sessions, sanitized patterns
- **Observability**: Application Insights + Log Analytics

## Directory Structure
- `infra/` - Infrastructure as Code (Bicep preferred)
- `mcp-server/` - MCP execution boundary
- `agent-orchestrator/` - Orchestrator API + agent loop + knowledge lookup
- `client-ui/` - Minimal web UI (trace-first)
- `shared/` - Shared telemetry + models
- `docs/architecture/` - Architecture contract (source of truth)
- `docs/prompts/` - Start/End prompts for session continuity

For more details, please refer to the [Architecture Overview](docs/architecture/00-overview.md).

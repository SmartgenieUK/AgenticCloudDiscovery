# Agent Orchestrator

## Purpose
The Orchestrator interprets user intent and coordinates tool execution via MCP. It is responsible for planning, confidence gating, retries (bounded), and response synthesis.

## API (MVP)
- `POST /chat`
  - input: session_id (optional), user message
  - output: final answer + execution trace summary

## Responsibilities
1.  **Reasoning & Planning**: Uses LLMs (GPT-4o, o3-mini) for intent extraction, tool selection, and planning.
2.  **Coordination**: Calls the MCP Server for tool execution. Never executes tools directly.
3.  **Confidence Gating**: Refuses execution if tool is unknown, docs confidence is low, or domain is disallowed.
4.  **Self-Healing**: Implements bounded retries for specific error classes (e.g., validation errors).
5.  **Tool Discovery**: Queries AI Search for missing tools (cold start).

See `docs/architecture/05-orchestrator-spec.md` for full specification.

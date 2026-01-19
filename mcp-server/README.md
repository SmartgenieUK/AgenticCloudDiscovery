# MCP Server

## Purpose
The MCP Server is the governed tool layer and the only execution boundary. It exposes:
- A tool registry (what tools exist and how to call them)
- Deterministic policy enforcement
- Schema validation
- Execution via APIM
- Structured logging and redaction

## Interfaces (MVP)
### Tool Listing
- Endpoint: `GET /tools`
- Returns: list of tool metadata (tool_id, name, description, args schema, allowed methods/domains)

### Tool Execution
- Endpoint: `POST /execute`
- Input (conceptual):
  - session_id (required)
  - tool_id (required)
  - args (required)
  - trace metadata (trace_id, agent_step, attempt)
- Output:
  - status (success/failure)
  - result payload (sanitized)
  - error object (structured) if failure
  - execution metadata (latency, status_code, request_id)

## Responsibilities
1.  **Policy Enforcement**: Evaluated before schema validation and execution (Domain allowlist, Method allowlist, Max payload size, etc.)
2.  **Validation**: Pydantic validation for tool args.
3.  **Execution Routing**: Route outbound execution through APIM.
4.  **Logging**: Structured logs with trace correlation.

See `docs/architecture/04-mcp-server-spec.md` for full specification.

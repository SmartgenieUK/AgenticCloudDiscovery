# MCP Server Specification (Execution Boundary)

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

### Health
- Endpoint: `GET /health`
- Returns: ok + dependency checks (optional)

## Policy Enforcement (Must-Have)
Policy is evaluated before schema validation and execution:
- Domain allowlist
- Method allowlist
- Max payload size
- Max execution timeouts
- Human approval requirement (if enabled)
- Logging redaction requirements

## Validation (Must-Have)
- Pydantic validation for tool args
- Reject malformed/missing args with 4xx response
- Enforce content-type rules for payloads (e.g., JSON only unless tool requires otherwise)

## Execution Routing
MCP Server must route outbound execution through APIM:
- Base URL: configured per environment
- API key/auth handled by APIM (preferred)
- MCP Server uses MI to call APIM where applicable

## Logging Requirements
Structured logs must include:
- timestamp
- session_id
- trace_id
- tool_id
- endpoint/domain
- method
- agent_step
- attempt
- status_code
- latency_ms
- error_class (if error)
- redaction_applied (true/false)

## Error Model
Standard error object:
- code (string)
- message (string)
- details (object)
- retryable (bool)
- policy_violation (bool)

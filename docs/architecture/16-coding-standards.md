# Coding Standards and Codex Guardrails

## Architecture Contract
The documents in `docs/architecture/` are the source of truth. Any architectural change requires updating these docs first, committing, and only then changing code.

## Codex Operating Rules
Codex (or any code generator) must:
- Work in small increments (1–3 files per iteration)
- Output complete file contents (no partial snippets)
- Provide exact run and test commands per iteration
- Add tests for policy enforcement and retry limits early
- Never embed secrets or keys in code or committed config
- Never move execution responsibilities into Orchestrator

Codex must not:
- Invent APIs, endpoints, or credentials
- Add new frameworks without justification and doc update
- Make broad refactors without a migration plan

## Code Quality Baseline
- Python: 3.11+
- Type hints where practical
- Structured logging (JSON preferred)
- Consistent error models and HTTP status usage
- Unit tests for key logic (policy, validation, retry budget)

## Security Baseline
- Redact sensitive fields in logs
- Domain allowlists and method allowlists enforced at MCP
- No direct external API calls from Orchestrator
- Approval gating for new tools (default on)

## Testing Baseline (MVP)
Minimum tests:
- MCP policy allow/deny
- MCP schema validation
- Orchestrator retry budget enforcement
- Orchestrator confidence gating refusal path (if implemented)

## Repo Conventions
- Keep services separated:
  - mcp-server/
  - agent-orchestrator/
  - client-ui/
  - infra/
- Shared utilities go in shared/ only if truly cross-cutting (telemetry, models)

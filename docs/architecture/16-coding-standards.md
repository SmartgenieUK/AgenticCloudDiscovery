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

## Daily Technical Checkpoints
At the end of every coding session, generate a checkpoint file and save it to `docs/techcheckpoint/`. This is mandatory for continuity across sessions and progress tracking.

**File naming:** `DailyCheckPoint_dd_mm_yyyy_hh_mm.md`

**Required sections:**
1. **Summary** — What was implemented and why (1-2 paragraphs)
2. **Files changed/added** — Table of every file touched with a short description
3. **How to run locally** — Exact commands and what success looks like
4. **Known issues / risks / TODOs** — Bullet list of open items
5. **Next 3 recommended increments** — Small, testable next steps
6. **Resume prompt** — A copy-paste block for the next session that includes: current milestone and status, what exists and is working, what to build next, and the guardrails to follow

**Process:** Use `docs/prompts/END_PROMPT.md` as the trigger. Commit the checkpoint file alongside any code changes.

## Repo Conventions
- Keep services separated:
  - mcp-server/
  - agent-orchestrator/
  - client-ui/
  - infra/
  - docs/techcheckpoint/
- Shared utilities go in shared/ only if truly cross-cutting (telemetry, models)

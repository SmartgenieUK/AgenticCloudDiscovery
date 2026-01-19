# Orchestrator Specification (Reasoning and Coordination)

## Purpose
The Orchestrator interprets user intent and coordinates tool execution via MCP. It is responsible for planning, confidence gating, retries (bounded), and response synthesis.

## API (MVP)
- `POST /chat`
  - input: session_id (optional), user message
  - output: final answer + execution trace summary

## Model Routing (Explicit)
- GPT-4o:
  - intent extraction
  - tool selection
  - response synthesis
- o3-mini or o1 (depending on availability):
  - multi-step planning
  - error analysis and self-healing

## Planning Loop Constraints (Must-Have)
- max_plan_steps (e.g., 6)
- max_tool_calls (e.g., 4)
- max_total_retries (from policy; do not exceed)
- token budget per session (best effort)

## Confidence Gating
Orchestrator must refuse execution if:
- tool is unknown and docs confidence is below threshold
- endpoint/method cannot be validated
- request appears to target disallowed domain
- the user intent is ambiguous for a destructive action

When refusing, it should ask for clarification or suggest safe alternatives.

## Self-Healing Strategy (MVP)
Applicable error classes:
- 400 validation errors where payload type/format mismatch is indicated
Non-retryable:
- 401/403 auth/permission
- 404 endpoint not found (unless docs indicate alternate)
- 429 rate limit (retry only if policy allows and with backoff)
- 5xx (bounded retries only)

Self-heal steps:
1. Read error response and classify error
2. Determine fix (e.g., int → string, missing field, incorrect JSON shape)
3. Apply fix
4. Retry (increment attempt) within policy limit
5. Log each attempt and outcome

## Tool Discovery Behavior (Cold Start)
If tool is missing:
- Query AI Search with a doc-grounded query
- Extract endpoint + schema requirements
- Draft a tool schema definition (pending approval)
- Do not publish without approval when approval gating is enabled

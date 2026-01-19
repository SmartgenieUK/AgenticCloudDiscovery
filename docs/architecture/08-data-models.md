# Data Models (MVP)

## Cosmos DB Containers
### policies
- policy_id (pk)
- version
- allowed_domains []
- allowed_methods []
- max_retries
- max_payload_bytes
- pii_blocklist []
- approval_required (bool)
- updated_at

### tools
- tool_id (pk)
- name
- description
- args_schema (json)
- allowed_domains []
- allowed_methods []
- status: pending|approved|disabled
- created_at, updated_at
- provenance: manual|generated
- source_docs []

### sessions
- session_id (pk)
- created_at, updated_at
- last_intent_summary (redacted)
- last_tool_used
- metrics: steps_count, tool_calls_count, retry_count
- model_routing_summary

### execution_patterns (optional)
- pattern_id (pk)
- tool_id
- sanitized_signature (hash)
- success_rate
- last_seen_at

## AI Search Index (Docs)
Recommended fields:
- id (key)
- title
- source
- version
- section
- chunk_text
- embedding (vector)
- tags
- created_at

## Required Request/Trace Fields (Shared Model)
- session_id
- trace_id
- tool_id
- agent_step
- attempt
- timestamp

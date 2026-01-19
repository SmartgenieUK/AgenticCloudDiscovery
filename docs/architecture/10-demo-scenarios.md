# Demo Scenarios (MVP)

## Scenario 1 — Cold Start Discovery
### Prompt
"Get me the user retention metrics from our CRM."

### Expected Behavior
- Orchestrator cannot find an existing tool for CRM retention.
- Orchestrator queries AI Search for CRM API docs.
- Orchestrator drafts tool definition and marks as pending.
- If approval is required:
  - Orchestrator asks for approval (or uses pre-approved demo tool)
- Once approved, tool executes via MCP → APIM → API.

### Success Criteria
- Tool creation is grounded in retrieved docs
- Execution is blocked until approval (if enabled)
- Trace shows session_id, tool_id, status_code

## Scenario 2 — Self-Healing Validation Error
### Prompt
"Update customer address for ID 123 to 10 Downing Street."

### Expected Behavior
- First attempt returns 400 due to schema mismatch (e.g., phone number type)
- Orchestrator classifies as retryable validation error
- Orchestrator corrects payload and retries within policy limit
- Second attempt succeeds

### Success Criteria
- Retry attempts are bounded
- Each attempt is logged and traceable
- Final response is correct and includes a trace summary

## Scenario 3 — Multi-Step Comparison (ROI)
### Prompt
"Compare sales from System A with marketing spend in System B and calculate ROI."

### Expected Behavior
- Orchestrator plans: fetch sales, fetch marketing spend, compute ROI
- Executes both via MCP tools
- Aggregates results and returns calculation

### Success Criteria
- Two tool executions appear in trace
- Calculation is transparent (inputs + formula)
- No raw PII persisted

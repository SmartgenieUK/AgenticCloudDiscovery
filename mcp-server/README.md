# MCP Server - Execution Boundary

The MCP (Model Control Plane) Server is the execution boundary for Agentic Cloud Discovery. It enforces policy rules, validates requests, injects authentication tokens, and routes all outbound API calls through APIM.

## Architecture

```
Orchestrator → MCP Server → APIM → Azure APIs
```

**Key Principles:**
- MCP is the ONLY component that calls external APIs
- Policy enforcement happens BEFORE execution
- Tokens are injected server-side (never exposed in logs)
- All requests are traced with correlation IDs

## API Endpoints

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "mcp-server",
  "version": "1.0.0",
  "stub_mode": true
}
```

### `GET /tools`
List all approved tools.

**Response:**
```json
{
  "tools": [
    {
      "tool_id": "inventory_discovery",
      "name": "Inventory Discovery",
      "description": "Discover Azure resources",
      "args_schema": {...},
      "allowed_methods": ["GET"],
      "allowed_domains": ["management.azure.com"],
      "status": "approved"
    }
  ]
}
```

### `POST /execute`
Execute a tool with policy enforcement.

**Request:**
```json
{
  "session_id": "session-123",
  "tool_id": "inventory_discovery",
  "args": {"subscription_id": "sub-123", "tenant_id": "tenant-123"},
  "connection_id": "conn-123",
  "trace_id": "trace-123",
  "correlation_id": "corr-123",
  "agent_step": 1,
  "attempt": 1
}
```

**Response (Success):**
```json
{
  "status": "success",
  "result": {
    "summary": "42 resources discovered",
    "counts": {"resources": 42}
  },
  "error": null,
  "metadata": {
    "latency_ms": 1234,
    "status_code": 200,
    "request_id": "req-123",
    "redaction_applied": false
  }
}
```

**Response (Failure):**
```json
{
  "status": "failure",
  "result": null,
  "error": {
    "code": "POLICY_VIOLATION",
    "message": "Tool is not approved for execution",
    "details": {"tool_id": "test_tool", "status": "pending"},
    "retryable": false,
    "policy_violation": true
  },
  "metadata": {
    "latency_ms": 0,
    "status_code": 403,
    "request_id": "req-123",
    "redaction_applied": false
  }
}
```

## Running Locally

### Prerequisites
- Python 3.11+
- Azure Cosmos DB (optional - will use in-memory if not configured)

### Setup
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your settings (optional - stub mode works without Cosmos)
```

### Start Server
```bash
# Start with stub mode (no Azure dependencies)
uvicorn main:app --reload --port 9000

# Or run directly
python main.py
```

Server will be available at `http://localhost:9000`

### Test Endpoints
```bash
# Health check
curl http://localhost:9000/health

# List tools (empty in stub mode without seeded data)
curl http://localhost:9000/tools

# Execute tool (requires connection and tool in Cosmos, or use in-memory seeding)
curl -X POST http://localhost:9000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "tool_id": "inventory_discovery",
    "args": {"subscription_id": "test-sub"},
    "connection_id": "test-conn",
    "attempt": 1
  }'
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_policy.py -v
```

## Configuration

See `.env.example` for all configuration options.

**Key Settings:**
- `APIM_STUB_MODE=true` - Run in stub mode without real APIM
- `COSMOS_ENDPOINT` - Cosmos DB endpoint (optional)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## Policy Enforcement

Policy is enforced BEFORE tool execution. The following checks are performed:

1. **Tool Approval**: Tool status must be "approved"
2. **Domain Allowlist**: Tool domains must be in policy allowlist
3. **Method Allowlist**: Tool HTTP methods must be in policy allowlist
4. **Payload Size**: Request payload must be under max_payload_bytes
5. **Retry Budget**: Attempt number must not exceed max_retries

If any check fails, a `POLICY_VIOLATION` error is returned with `retryable=false`.

## Security

- **Tokens**: Access tokens are NEVER logged or exposed in error messages
- **Token Injection**: Tokens are injected server-side from Connections
- **Token Expiry**: Expired tokens are rejected before execution
- **Correlation IDs**: All requests are traceable via correlation_id, trace_id, session_id

## Development

**Project Structure:**
```
mcp-server/
├── main.py              # FastAPI app with endpoints
├── config.py            # Configuration settings
├── models.py            # Pydantic models
├── policy.py            # Policy enforcement logic
├── executor.py          # Tool execution with APIM routing
├── repositories.py      # Data access layer (Cosmos + in-memory)
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── tests/               # Unit tests
    ├── test_policy.py
    ├── test_executor.py
    └── test_repositories.py
```

## Integration with Orchestrator

The orchestrator calls MCP Server like this:

```python
import httpx

mcp_url = "http://localhost:9000/execute"
payload = {
    "session_id": session_id,
    "tool_id": "inventory_discovery",
    "args": {"subscription_id": "sub-123"},
    "connection_id": "conn-123",
    "trace_id": trace_id,
    "correlation_id": correlation_id,
    "attempt": 1
}

response = httpx.post(mcp_url, json=payload, timeout=30.0)
result = response.json()

if result["status"] == "success":
    print(f"Tool executed: {result['result']}")
else:
    print(f"Tool failed: {result['error']}")
```

## Next Steps

- [ ] Deploy to Azure Container Apps (Phase 3)
- [ ] Integrate Application Insights telemetry
- [ ] Add self-healing logic for 400 errors (Phase 5)
- [ ] Implement tool approval workflow (Phase 4)

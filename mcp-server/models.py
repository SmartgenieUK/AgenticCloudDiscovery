"""Pydantic models for MCP Server API."""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ExecuteToolRequest(BaseModel):
    """Request model for tool execution."""
    session_id: str = Field(..., description="Session identifier for correlation")
    tool_id: str = Field(..., description="Tool identifier to execute")
    args: Dict[str, Any] = Field(..., description="Tool arguments")
    connection_id: str = Field(..., description="Connection ID for token injection")
    trace_id: Optional[str] = Field(None, description="Distributed trace identifier")
    correlation_id: Optional[str] = Field(None, description="End-to-end correlation ID")
    agent_step: int = Field(1, description="Step number in execution plan")
    attempt: int = Field(1, description="Retry attempt number")
    access_token: Optional[str] = Field(None, description="Pre-acquired bearer token (passed from orchestrator)")


class ExecutionMetadata(BaseModel):
    """Metadata about tool execution."""
    latency_ms: int
    status_code: Optional[int] = None
    request_id: str
    redaction_applied: bool = False


class ErrorResponse(BaseModel):
    """Structured error response."""
    code: str = Field(..., description="Error code (POLICY_VIOLATION, AUTH_FAILED, etc.)")
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")
    retryable: bool = Field(False, description="Whether the error is retryable")
    policy_violation: bool = Field(False, description="Whether this is a policy violation")


class ExecuteToolResponse(BaseModel):
    """Response model for tool execution."""
    status: str = Field(..., description="success or failure")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool execution result (sanitized)")
    error: Optional[ErrorResponse] = Field(None, description="Error details if failed")
    metadata: ExecutionMetadata


class ToolSchema(BaseModel):
    """Tool definition schema."""
    tool_id: str
    name: str
    description: str
    args_schema: Dict[str, Any]
    allowed_methods: List[str]
    allowed_domains: List[str]
    status: str = Field(..., description="approved, pending, or disabled")
    provenance: Optional[str] = Field(None, description="manual or generated")
    source_docs: Optional[List[str]] = Field(None, description="Source documentation references")
    category: Optional[str] = Field(None, description="Service category: inventory, compute, storage, databases, networking, app_services, addon")
    provider_namespace: Optional[str] = Field(None, description="Azure provider namespace, e.g. Microsoft.Compute")


class ToolListResponse(BaseModel):
    """Response model for tool listing."""
    tools: List[ToolSchema]


class PolicyDocument(BaseModel):
    """Policy definition schema."""
    policy_id: str
    allowed_domains: List[str]
    allowed_methods: List[str]
    max_payload_bytes: int
    max_retries: int
    approval_required: bool
    max_execution_timeout_ms: int = 30000


class ConnectionDocument(BaseModel):
    """Connection document from Cosmos."""
    connection_id: str
    user_id: str
    tenant_id: str
    subscription_ids: List[str]
    provider: str
    access_token: str  # NEVER log this
    token_expiry: Optional[str] = None
    rbac_tier: str
    status: str

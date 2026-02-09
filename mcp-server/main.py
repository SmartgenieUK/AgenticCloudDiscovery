"""MCP Server - Execution Boundary with Policy Enforcement."""
import logging
import uuid
from typing import Dict
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from models import (
    ExecuteToolRequest,
    ExecuteToolResponse,
    ToolListResponse,
    ToolSchema,
    ErrorResponse,
    ExecutionMetadata
)
from repositories import connection_repo, tool_repo, policy_repo
from policy import create_policy_enforcer
from executor import create_executor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Execution boundary with policy enforcement for Agentic Cloud Discovery",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize executor
executor = create_executor()

logger.info("MCP Server initialized successfully")


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to all requests."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.get("/health")
async def health_check() -> Dict:
    """
    Health check endpoint.

    Returns:
        Status and basic info about the service.
    """
    return {
        "status": "ok",
        "service": "mcp-server",
        "version": "1.0.0",
        "stub_mode": settings.apim_stub_mode
    }


@app.get("/tools", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """
    List all approved tools.

    Only returns tools with status='approved'.
    """
    logger.info("Listing approved tools")

    try:
        approved_tools = tool_repo.list_approved()
        logger.info(f"Found {len(approved_tools)} approved tools")

        # Convert to ToolSchema models
        tools = [
            ToolSchema(
                tool_id=tool["tool_id"],
                name=tool.get("name", tool["tool_id"]),
                description=tool.get("description", ""),
                args_schema=tool.get("args_schema", {}),
                allowed_methods=tool.get("allowed_methods", []),
                allowed_domains=tool.get("allowed_domains", []),
                status=tool.get("status", "approved"),
                provenance=tool.get("provenance"),
                source_docs=tool.get("source_docs")
            )
            for tool in approved_tools
        ]

        return ToolListResponse(tools=tools)

    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tools: {str(e)}"
        )


@app.post("/execute", response_model=ExecuteToolResponse)
async def execute_tool(request: ExecuteToolRequest, http_request: Request) -> ExecuteToolResponse:
    """
    Execute a tool with policy enforcement.

    Steps:
    1. Load policy
    2. Load tool definition
    3. Enforce policy rules
    4. Load connection (for token)
    5. Execute tool via APIM
    6. Return sanitized result

    All errors are structured with retryable flag.
    """
    correlation_id = http_request.state.correlation_id
    logger.info(
        f"Execute tool request: tool_id={request.tool_id}, connection_id={request.connection_id}, "
        f"session_id={request.session_id}, attempt={request.attempt}, correlation_id={correlation_id}"
    )

    try:
        # Step 1: Load policy
        policy = policy_repo.get_default()
        enforcer = create_policy_enforcer(policy)
        logger.info(f"Loaded policy: {policy.get('policy_id')}")

        # Step 2: Load tool definition
        tool = tool_repo.get_by_id(request.tool_id)
        if not tool:
            logger.warning(f"Tool {request.tool_id} not found in registry")
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=ErrorResponse(
                    code="VALIDATION_ERROR",
                    message=f"Tool {request.tool_id} not found in registry",
                    details={"tool_id": request.tool_id},
                    retryable=False,
                    policy_violation=False
                ),
                metadata=ExecutionMetadata(
                    latency_ms=0,
                    status_code=404,
                    request_id=str(uuid.uuid4()),
                    redaction_applied=False
                )
            )

        # Step 3: Enforce policy rules
        is_valid, error = enforcer.enforce(request, tool)
        if not is_valid:
            logger.warning(f"Policy enforcement failed: {error.message}")
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=error,
                metadata=ExecutionMetadata(
                    latency_ms=0,
                    status_code=403,
                    request_id=str(uuid.uuid4()),
                    redaction_applied=False
                )
            )

        # Step 4: Load connection for token injection
        connection = connection_repo.get_by_id(request.connection_id)
        if not connection:
            logger.warning(f"Connection {request.connection_id} not found")
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=ErrorResponse(
                    code="AUTH_FAILED",
                    message=f"Connection {request.connection_id} not found",
                    details={"connection_id": request.connection_id},
                    retryable=False,
                    policy_violation=False
                ),
                metadata=ExecutionMetadata(
                    latency_ms=0,
                    status_code=404,
                    request_id=str(uuid.uuid4()),
                    redaction_applied=False
                )
            )

        # Step 5: Execute tool
        logger.info(f"Policy enforcement passed, executing tool {request.tool_id}")
        response = executor.execute(request, tool, connection)

        # Log execution result (NEVER log token or sensitive data)
        logger.info(
            f"Tool execution completed: status={response.status}, "
            f"status_code={response.metadata.status_code}, "
            f"latency_ms={response.metadata.latency_ms}, "
            f"correlation_id={correlation_id}"
        )

        return response

    except Exception as e:
        logger.error(f"Unexpected error during tool execution: {e}", exc_info=True)
        return ExecuteToolResponse(
            status="failure",
            result=None,
            error=ErrorResponse(
                code="EXECUTION_ERROR",
                message=f"Unexpected error: {str(e)}",
                details={"exception": str(e)},
                retryable=False,
                policy_violation=False
            ),
            metadata=ExecutionMetadata(
                latency_ms=0,
                status_code=500,
                request_id=str(uuid.uuid4()),
                redaction_applied=False
            )
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=settings.log_level.lower()
    )

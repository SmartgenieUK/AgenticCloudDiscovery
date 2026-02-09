"""Tool executor with APIM routing and token injection."""
import logging
import time
import uuid
from typing import Dict, Optional, Tuple
from datetime import datetime
import httpx
from models import ExecuteToolRequest, ExecuteToolResponse, ExecutionMetadata, ErrorResponse
from config import settings

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools with APIM routing and token injection."""

    def __init__(self, apim_base_url: Optional[str], stub_mode: bool, timeout: float):
        self.apim_base_url = apim_base_url
        self.stub_mode = stub_mode
        self.timeout = timeout
        logger.info(f"ToolExecutor initialized (stub_mode={stub_mode}, apim_base_url={apim_base_url})")

    def inject_token(self, connection: Dict, headers: Dict[str, str]) -> Tuple[bool, Optional[ErrorResponse]]:
        """
        Inject access token from connection into Authorization header.

        CRITICAL: Token is NEVER logged or exposed in error messages.
        """
        access_token = connection.get("access_token")

        if not access_token:
            logger.error(f"Connection {connection.get('connection_id')} has no access_token")
            return False, ErrorResponse(
                code="AUTH_FAILED",
                message="Connection does not have a valid access token",
                details={"connection_id": connection.get("connection_id")},
                retryable=False,
                policy_violation=False
            )

        # Check token expiry if available
        token_expiry = connection.get("token_expiry")
        if token_expiry:
            try:
                expiry_dt = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
                if expiry_dt < datetime.now(expiry_dt.tzinfo):
                    logger.warning(f"Token expired for connection {connection.get('connection_id')}")
                    return False, ErrorResponse(
                        code="AUTH_FAILED",
                        message="Access token has expired, please re-authenticate",
                        details={"connection_id": connection.get("connection_id"), "expired_at": token_expiry},
                        retryable=False,
                        policy_violation=False
                    )
            except Exception as e:
                logger.warning(f"Failed to parse token expiry: {e}")

        # Inject token into Authorization header
        headers["Authorization"] = f"Bearer {access_token}"
        logger.info(f"Token injected for connection {connection.get('connection_id')} (NEVER LOGGED)")

        return True, None

    def build_apim_url(self, tool: Dict, args: Dict) -> str:
        """Build APIM URL for the tool execution."""
        # In real implementation, this would:
        # 1. Extract endpoint from tool definition
        # 2. Substitute path parameters from args
        # 3. Construct full APIM URL

        # For MVP stub: return a mock Azure ARM endpoint
        endpoint = tool.get("endpoint", "/subscriptions")
        subscription_id = args.get("subscription_id", "default-subscription")

        if self.stub_mode or not self.apim_base_url:
            # Return mock endpoint for stub mode
            return f"https://management.azure.com{endpoint}"

        # Real APIM routing
        return f"{self.apim_base_url}{endpoint}"

    def execute_stub(self, request: ExecuteToolRequest, tool: Dict) -> ExecuteToolResponse:
        """Execute tool in stub mode (returns mock response)."""
        logger.info(f"Executing tool {request.tool_id} in STUB mode")

        start_time = time.time()
        time.sleep(0.1)  # Simulate network latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Return mock Azure response
        mock_result = {
            "summary": f"{request.tool_id} executed successfully in stub mode",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "scope": {
                "tenant_id": request.args.get("tenant_id"),
                "subscription_id": request.args.get("subscription_id")
            },
            "counts": {
                "resources": 42
            },
            "stub": True
        }

        return ExecuteToolResponse(
            status="success",
            result=mock_result,
            error=None,
            metadata=ExecutionMetadata(
                latency_ms=latency_ms,
                status_code=200,
                request_id=str(uuid.uuid4()),
                redaction_applied=False
            )
        )

    def execute_real(
        self,
        request: ExecuteToolRequest,
        tool: Dict,
        connection: Dict
    ) -> ExecuteToolResponse:
        """Execute tool via APIM with real HTTP call."""
        logger.info(f"Executing tool {request.tool_id} via APIM (attempt {request.attempt})")

        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Build headers with correlation IDs
        headers = {
            "Content-Type": "application/json",
            "X-Trace-ID": request.trace_id or str(uuid.uuid4()),
            "X-Correlation-ID": request.correlation_id or str(uuid.uuid4()),
            "X-Session-ID": request.session_id,
            "X-Request-ID": request_id
        }

        # Inject token from connection (NEVER logged)
        success, error = self.inject_token(connection, headers)
        if not success:
            latency_ms = int((time.time() - start_time) * 1000)
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=error,
                metadata=ExecutionMetadata(
                    latency_ms=latency_ms,
                    status_code=401,
                    request_id=request_id,
                    redaction_applied=False
                )
            )

        # Build APIM URL
        url = self.build_apim_url(tool, request.args)

        # Execute HTTP request
        try:
            method = tool.get("allowed_methods", ["GET"])[0]  # Use first allowed method
            logger.info(f"Calling APIM: {method} {url} (session_id={request.session_id})")

            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=headers, params=request.args)
                elif method == "POST":
                    response = client.post(url, headers=headers, json=request.args)
                elif method == "PUT":
                    response = client.put(url, headers=headers, json=request.args)
                elif method == "PATCH":
                    response = client.patch(url, headers=headers, json=request.args)
                elif method == "DELETE":
                    response = client.delete(url, headers=headers, params=request.args)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"APIM response: status={response.status_code}, latency={latency_ms}ms")

            # Handle response
            if response.status_code >= 200 and response.status_code < 300:
                # Success
                result = response.json() if response.content else {}
                return ExecuteToolResponse(
                    status="success",
                    result=result,
                    error=None,
                    metadata=ExecutionMetadata(
                        latency_ms=latency_ms,
                        status_code=response.status_code,
                        request_id=request_id,
                        redaction_applied=False
                    )
                )
            else:
                # HTTP error
                error_message = response.text or f"HTTP {response.status_code}"
                retryable = response.status_code >= 500 or response.status_code == 429

                return ExecuteToolResponse(
                    status="failure",
                    result=None,
                    error=ErrorResponse(
                        code="EXECUTION_ERROR",
                        message=f"Tool execution failed: {error_message}",
                        details={"status_code": response.status_code, "response": error_message[:500]},
                        retryable=retryable,
                        policy_violation=False
                    ),
                    metadata=ExecutionMetadata(
                        latency_ms=latency_ms,
                        status_code=response.status_code,
                        request_id=request_id,
                        redaction_applied=False
                    )
                )

        except httpx.TimeoutException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"APIM call timed out after {self.timeout}s: {e}")
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=ErrorResponse(
                    code="EXECUTION_ERROR",
                    message=f"Tool execution timed out after {self.timeout}s",
                    details={"timeout_seconds": self.timeout},
                    retryable=True,  # Timeout is retryable
                    policy_violation=False
                ),
                metadata=ExecutionMetadata(
                    latency_ms=latency_ms,
                    status_code=None,
                    request_id=request_id,
                    redaction_applied=False
                )
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"APIM call failed with exception: {e}")
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=ErrorResponse(
                    code="EXECUTION_ERROR",
                    message=f"Tool execution failed: {str(e)}",
                    details={"exception": str(e)},
                    retryable=False,
                    policy_violation=False
                ),
                metadata=ExecutionMetadata(
                    latency_ms=latency_ms,
                    status_code=None,
                    request_id=request_id,
                    redaction_applied=False
                )
            )

    def execute(
        self,
        request: ExecuteToolRequest,
        tool: Dict,
        connection: Dict
    ) -> ExecuteToolResponse:
        """
        Execute tool with APIM routing and token injection.

        This is the main entry point for tool execution.
        """
        if self.stub_mode:
            return self.execute_stub(request, tool)
        else:
            return self.execute_real(request, tool, connection)


def create_executor() -> ToolExecutor:
    """Factory function to create a tool executor."""
    return ToolExecutor(
        apim_base_url=settings.apim_base_url,
        stub_mode=settings.apim_stub_mode,
        timeout=settings.apim_timeout_seconds
    )

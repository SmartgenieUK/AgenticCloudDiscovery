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

ARM_BASE_URL = "https://management.azure.com"


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

    def build_arm_url(self, tool: Dict, args: Dict) -> str:
        """Build Azure ARM API URL from tool definition and args."""
        endpoint = tool.get("endpoint", "/subscriptions")
        api_version = tool.get("api_version", "2021-04-01")

        # Substitute path parameters from args
        subscription_id = args.get("subscription_id", "")
        endpoint = endpoint.replace("{subscription_id}", subscription_id)

        # Use APIM if configured, otherwise direct ARM
        base = self.apim_base_url if self.apim_base_url else ARM_BASE_URL
        url = f"{base}{endpoint}?api-version={api_version}"
        return url

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
        """Execute tool via ARM API with real HTTP call."""
        logger.info(f"Executing tool {request.tool_id} via ARM API (attempt {request.attempt})")

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

        # Build ARM URL from tool definition
        url = self.build_arm_url(tool, request.args)

        # Execute HTTP request
        try:
            method = tool.get("allowed_methods", ["GET"])[0]
            logger.info(f"Calling ARM API: {method} {url} (session_id={request.session_id})")

            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
                    # For cost queries, build proper request body
                    body = self._build_request_body(request.tool_id, request.args)
                    response = client.post(url, headers=headers, json=body)
                elif method == "PUT":
                    response = client.put(url, headers=headers, json=request.args)
                elif method == "PATCH":
                    response = client.patch(url, headers=headers, json=request.args)
                elif method == "DELETE":
                    response = client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"ARM API response: status={response.status_code}, latency={latency_ms}ms")

            # Handle response
            if 200 <= response.status_code < 300:
                raw_result = response.json() if response.content else {}
                # Wrap ARM response in our expected format
                result = self._normalize_arm_response(request.tool_id, raw_result)
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
                error_message = response.text or f"HTTP {response.status_code}"
                retryable = response.status_code >= 500 or response.status_code == 429

                return ExecuteToolResponse(
                    status="failure",
                    result=None,
                    error=ErrorResponse(
                        code="EXECUTION_ERROR",
                        message=f"ARM API call failed: {error_message[:500]}",
                        details={"status_code": response.status_code},
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
            logger.error(f"ARM API call timed out after {self.timeout}s: {e}")
            return ExecuteToolResponse(
                status="failure",
                result=None,
                error=ErrorResponse(
                    code="EXECUTION_ERROR",
                    message=f"Tool execution timed out after {self.timeout}s",
                    details={"timeout_seconds": self.timeout},
                    retryable=True,
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
            logger.error(f"ARM API call failed with exception: {e}")
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

    def _build_request_body(self, tool_id: str, args: Dict) -> Dict:
        """Build request body for POST-based ARM APIs (e.g. cost query)."""
        if tool_id == "cost_discovery":
            return {
                "type": "ActualCost",
                "dataSet": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {"name": "Cost", "function": "Sum"},
                        "totalCostUSD": {"name": "CostUSD", "function": "Sum"},
                    },
                    "grouping": [
                        {"type": "Dimension", "name": "ServiceName"},
                    ],
                },
                "timeframe": "MonthToDate",
            }
        return {}

    def _normalize_arm_response(self, tool_id: str, raw: Dict) -> Dict:
        """Normalize ARM API response into our expected format with summary and counts."""
        if tool_id == "inventory_discovery":
            resources = raw.get("value", [])
            type_counts = {}
            for r in resources:
                rtype = r.get("type", "unknown")
                type_counts[rtype] = type_counts.get(rtype, 0) + 1
            return {
                "summary": f"Found {len(resources)} resources across {len(type_counts)} types",
                "counts": {"resources": len(resources), "types": len(type_counts)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": resources,
                "type_breakdown": type_counts,
            }
        elif tool_id == "cost_discovery":
            rows = raw.get("properties", {}).get("rows", [])
            return {
                "summary": f"Cost query returned {len(rows)} line items",
                "counts": {"line_items": len(rows)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "raw_cost_data": raw,
            }
        elif tool_id == "security_discovery":
            assessments = raw.get("value", [])
            return {
                "summary": f"Found {len(assessments)} security assessments",
                "counts": {"assessments": len(assessments)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "assessments": assessments,
            }
        # Fallback: return raw with defaults
        return {
            "summary": f"{tool_id} completed",
            "counts": {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "raw": raw,
        }

    def execute(
        self,
        request: ExecuteToolRequest,
        tool: Dict,
        connection: Dict,
        force_real: bool = False,
    ) -> ExecuteToolResponse:
        """
        Execute tool with APIM routing and token injection.

        Args:
            force_real: If True, bypass stub mode (used when a real token is available)
        """
        if self.stub_mode and not force_real:
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

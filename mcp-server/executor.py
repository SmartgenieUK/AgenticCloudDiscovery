"""Tool executor with APIM routing and token injection."""
import logging
import time
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import httpx
from models import ExecuteToolRequest, ExecuteToolResponse, ExecutionMetadata, ErrorResponse
from config import settings

logger = logging.getLogger(__name__)

ARM_BASE_URL = "https://management.azure.com"

# Max pages to prevent infinite loops
MAX_RG_PAGES = 100


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

    @staticmethod
    def _parse_throttle_headers(headers: httpx.Headers) -> Tuple[Optional[int], Optional[float]]:
        """Parse Resource Graph throttle headers.

        Returns:
            (remaining_quota, resets_after_seconds) — either may be None.
        """
        remaining = None
        resets_after = None

        raw_remaining = headers.get("x-ms-user-quota-remaining")
        if raw_remaining is not None:
            try:
                remaining = int(raw_remaining)
            except (ValueError, TypeError):
                pass

        raw_resets = headers.get("x-ms-user-quota-resets-after")
        if raw_resets:
            try:
                # Format: HH:MM:SS
                parts = raw_resets.split(":")
                if len(parts) == 3:
                    resets_after = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            except (ValueError, TypeError):
                pass

        return remaining, resets_after

    def _execute_resource_graph(
        self,
        request: ExecuteToolRequest,
        tool: Dict,
        headers: Dict[str, str],
        subscription_ids: List[str],
    ) -> Tuple[List[Dict], int]:
        """Execute Resource Graph query with $skipToken pagination loop.

        Returns:
            (all_resources, total_records)
        """
        kql = tool.get("kql_template", "resources")
        base = self.apim_base_url if self.apim_base_url else ARM_BASE_URL
        url = f"{base}{tool['endpoint']}?api-version={tool['api_version']}"

        all_resources: List[Dict] = []
        skip_token: Optional[str] = None
        page = 0

        while page < MAX_RG_PAGES:
            page += 1
            body = {
                "subscriptions": subscription_ids,
                "query": kql,
                "options": {
                    "resultFormat": "objectArray",
                    "$top": 1000,
                },
            }
            if skip_token:
                body["options"]["$skipToken"] = skip_token

            logger.info(
                "resource_graph_query page=%d tool=%s subs=%d trace_id=%s",
                page, request.tool_id, len(subscription_ids),
                request.trace_id or "",
            )

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=body)

            # Handle 429 throttling
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "5")
                try:
                    wait = float(retry_after)
                except (ValueError, TypeError):
                    wait = 5.0
                logger.warning("resource_graph_throttled retry_after=%.1fs tool=%s", wait, request.tool_id)
                time.sleep(wait)
                page -= 1  # Retry same page
                continue

            response.raise_for_status()
            result = response.json()

            data = result.get("data", [])
            all_resources.extend(data)

            # Proactive throttle handling
            remaining, resets_after = self._parse_throttle_headers(response.headers)
            if remaining is not None and remaining < 2 and resets_after:
                logger.warning(
                    "resource_graph_quota_low remaining=%d resets_after=%.1fs",
                    remaining, resets_after,
                )
                time.sleep(min(resets_after, 10.0))

            skip_token = result.get("$skipToken")
            if not skip_token:
                break

        total_records = result.get("totalRecords", len(all_resources)) if page > 0 else len(all_resources)
        logger.info(
            "resource_graph_complete tool=%s pages=%d resources=%d total_records=%d",
            request.tool_id, page, len(all_resources), total_records,
        )
        return all_resources, total_records

    def _normalize_rg_response(self, tool_id: str, resources: List[Dict], total_records: int) -> Dict:
        """Normalize Resource Graph results into our standard format."""
        timestamp = datetime.utcnow().isoformat() + "Z"

        if tool_id == "rg_inventory_discovery":
            type_counts: Dict[str, int] = {}
            for r in resources:
                rtype = r.get("type", "unknown")
                type_counts[rtype] = type_counts.get(rtype, 0) + 1
            return {
                "summary": f"Found {len(resources)} resources across {len(type_counts)} types via Resource Graph",
                "counts": {"resources": len(resources), "types": len(type_counts)},
                "timestamp": timestamp,
                "resources": resources,
                "type_breakdown": type_counts,
                "total_records": total_records,
            }

        elif tool_id == "rg_topology_discovery":
            type_counts = {}
            for r in resources:
                rtype = r.get("type", "unknown")
                type_counts[rtype] = type_counts.get(rtype, 0) + 1
            return {
                "summary": f"Found {len(resources)} network resources across {len(type_counts)} types via Resource Graph",
                "counts": {"resources": len(resources), "types": len(type_counts)},
                "timestamp": timestamp,
                "resources": resources,
                "type_breakdown": type_counts,
                "total_records": total_records,
            }

        elif tool_id == "rg_identity_discovery":
            assignments = [r for r in resources if "roleassignments" in r.get("type", "").lower()]
            definitions = [r for r in resources if "roledefinitions" in r.get("type", "").lower()]
            return {
                "summary": f"Found {len(resources)} identity resources ({len(assignments)} assignments, {len(definitions)} definitions) via Resource Graph",
                "counts": {"role_assignments": len(assignments), "role_definitions": len(definitions)},
                "timestamp": timestamp,
                "resources": resources,
                "total_records": total_records,
            }

        elif tool_id == "rg_policy_discovery":
            return {
                "summary": f"Found {len(resources)} policy assignments via Resource Graph",
                "counts": {"policy_assignments": len(resources)},
                "timestamp": timestamp,
                "resources": resources,
                "total_records": total_records,
            }

        # Fallback
        return {
            "summary": f"{tool_id} returned {len(resources)} resources",
            "counts": {"resources": len(resources)},
            "timestamp": timestamp,
            "resources": resources,
            "total_records": total_records,
        }

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

        # Dispatch: Resource Graph tools use pagination loop, others use standard ARM
        if tool.get("kql_template"):
            kql = tool.get("kql_template", "")
            try:
                # Resource Graph execution path
                subscription_ids = request.args.get(
                    "subscription_ids",
                    [request.args["subscription_id"]] if request.args.get("subscription_id") else [],
                )
                logger.info("resource_graph_kql tool=%s kql=%s subs=%s", request.tool_id, kql, subscription_ids)
                resources, total_records = self._execute_resource_graph(
                    request, tool, headers, subscription_ids,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                result = self._normalize_rg_response(request.tool_id, resources, total_records)
                result["kql_query"] = kql
                return ExecuteToolResponse(
                    status="success",
                    result=result,
                    error=None,
                    metadata=ExecutionMetadata(
                        latency_ms=latency_ms,
                        status_code=200,
                        request_id=request_id,
                        redaction_applied=False
                    )
                )
            except Exception as rg_exc:
                latency_ms = int((time.time() - start_time) * 1000)
                logger.error("resource_graph_failed tool=%s error=%s kql=%s", request.tool_id, rg_exc, kql)
                return ExecuteToolResponse(
                    status="failure",
                    result={"kql_query": kql},
                    error=ErrorResponse(
                        code="EXECUTION_ERROR",
                        message=f"Resource Graph query failed: {str(rg_exc)}",
                        details={"exception": str(rg_exc), "kql_query": kql},
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

        try:
            # Standard ARM API execution path
            url = self.build_arm_url(tool, request.args)
            method = tool.get("allowed_methods", ["GET"])[0]
            logger.info(f"Calling ARM API: {method} {url} (session_id={request.session_id})")

            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
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
        """Build request body for POST-based ARM APIs (e.g. cost query).

        Note: Resource Graph tools bypass this method — their body is built
        inside _execute_resource_graph() which handles pagination.
        """
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
        elif tool_id == "compute_discovery":
            vms = raw.get("value", [])
            return {
                "summary": f"Found {len(vms)} virtual machines",
                "counts": {"virtual_machines": len(vms)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": vms,
            }
        elif tool_id == "storage_discovery":
            accounts = raw.get("value", [])
            return {
                "summary": f"Found {len(accounts)} storage accounts",
                "counts": {"storage_accounts": len(accounts)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": accounts,
            }
        elif tool_id == "database_discovery":
            servers = raw.get("value", [])
            return {
                "summary": f"Found {len(servers)} SQL servers",
                "counts": {"sql_servers": len(servers)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": servers,
            }
        elif tool_id == "networking_discovery":
            vnets = raw.get("value", [])
            return {
                "summary": f"Found {len(vnets)} virtual networks",
                "counts": {"virtual_networks": len(vnets)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": vnets,
            }
        elif tool_id == "appservice_discovery":
            apps = raw.get("value", [])
            return {
                "summary": f"Found {len(apps)} web/function apps",
                "counts": {"web_apps": len(apps)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": apps,
            }
        # --- Layer 2: Topology normalizers ---
        elif tool_id == "nic_discovery":
            nics = raw.get("value", [])
            return {
                "summary": f"Found {len(nics)} network interfaces",
                "counts": {"nics": len(nics)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": nics,
            }
        elif tool_id == "nsg_discovery":
            nsgs = raw.get("value", [])
            return {
                "summary": f"Found {len(nsgs)} network security groups",
                "counts": {"nsgs": len(nsgs)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": nsgs,
            }
        elif tool_id == "public_ip_discovery":
            pips = raw.get("value", [])
            return {
                "summary": f"Found {len(pips)} public IP addresses",
                "counts": {"public_ips": len(pips)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": pips,
            }
        elif tool_id == "vnet_peering_discovery":
            vnets = raw.get("value", [])
            return {
                "summary": f"Found {len(vnets)} virtual networks with peerings",
                "counts": {"vnets_with_peerings": len(vnets)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": vnets,
            }
        elif tool_id == "route_table_discovery":
            tables = raw.get("value", [])
            return {
                "summary": f"Found {len(tables)} route tables",
                "counts": {"route_tables": len(tables)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": tables,
            }
        elif tool_id == "private_endpoint_discovery":
            endpoints = raw.get("value", [])
            return {
                "summary": f"Found {len(endpoints)} private endpoints",
                "counts": {"private_endpoints": len(endpoints)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": endpoints,
            }
        elif tool_id == "load_balancer_discovery":
            lbs = raw.get("value", [])
            return {
                "summary": f"Found {len(lbs)} load balancers",
                "counts": {"load_balancers": len(lbs)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": lbs,
            }
        # --- Layer 3: Identity & Access normalizers ---
        elif tool_id == "role_assignment_discovery":
            assignments = raw.get("value", [])
            return {
                "summary": f"Found {len(assignments)} role assignments",
                "counts": {"role_assignments": len(assignments)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": assignments,
            }
        elif tool_id == "role_definition_discovery":
            definitions = raw.get("value", [])
            return {
                "summary": f"Found {len(definitions)} role definitions",
                "counts": {"role_definitions": len(definitions)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": definitions,
            }
        elif tool_id == "policy_assignment_discovery":
            policies = raw.get("value", [])
            return {
                "summary": f"Found {len(policies)} policy assignments",
                "counts": {"policy_assignments": len(policies)},
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "resources": policies,
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
        """Execute tool via ARM API with token injection."""
        return self.execute_real(request, tool, connection)


def create_executor() -> ToolExecutor:
    """Factory function to create a tool executor."""
    return ToolExecutor(
        apim_base_url=settings.apim_base_url,
        stub_mode=settings.apim_stub_mode,
        timeout=settings.apim_timeout_seconds
    )

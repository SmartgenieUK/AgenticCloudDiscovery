"""MCP client for tool execution with retry logic."""
import datetime
import logging
import time
from typing import Dict, Optional

import httpx
from fastapi import HTTPException, status

from config import settings

logger = logging.getLogger("agent-orchestrator.mcp.client")


STUB_RESOURCES = {
    "inventory_discovery": [
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web-01", "name": "vm-web-01", "type": "Microsoft.Compute/virtualMachines", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-api-01", "name": "vm-api-01", "type": "Microsoft.Compute/virtualMachines", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/stproddata01", "name": "stproddata01", "type": "Microsoft.Storage/storageAccounts", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/stprodlogs", "name": "stprodlogs", "type": "Microsoft.Storage/storageAccounts", "location": "westus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-prod-01", "name": "sql-prod-01", "type": "Microsoft.Sql/servers", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod", "name": "vnet-prod", "type": "Microsoft.Network/virtualNetworks", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/networkSecurityGroups/nsg-web", "name": "nsg-web", "type": "Microsoft.Network/networkSecurityGroups", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Web/sites/app-frontend", "name": "app-frontend", "type": "Microsoft.Web/sites", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Web/sites/app-api", "name": "app-api", "type": "Microsoft.Web/sites", "location": "eastus"},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/disks/disk-web-01-os", "name": "disk-web-01-os", "type": "Microsoft.Compute/disks", "location": "eastus"},
    ],
    "compute_discovery": [
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web-01", "name": "vm-web-01", "type": "Microsoft.Compute/virtualMachines", "location": "eastus", "properties": {"vmSize": "Standard_D4s_v3", "osProfile": {"computerName": "vm-web-01", "adminUsername": "azadmin"}, "storageProfile": {"osDisk": {"osType": "Linux", "diskSizeGB": 128}}, "provisioningState": "Succeeded"}},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-api-01", "name": "vm-api-01", "type": "Microsoft.Compute/virtualMachines", "location": "eastus", "properties": {"vmSize": "Standard_D2s_v3", "osProfile": {"computerName": "vm-api-01", "adminUsername": "azadmin"}, "storageProfile": {"osDisk": {"osType": "Linux", "diskSizeGB": 64}}, "provisioningState": "Succeeded"}},
    ],
    "storage_discovery": [
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/stproddata01", "name": "stproddata01", "type": "Microsoft.Storage/storageAccounts", "location": "eastus", "kind": "StorageV2", "sku": {"name": "Standard_LRS"}, "properties": {"accessTier": "Hot", "supportsHttpsTrafficOnly": True, "encryption": {"services": {"blob": {"enabled": True}}}}},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Storage/storageAccounts/stprodlogs", "name": "stprodlogs", "type": "Microsoft.Storage/storageAccounts", "location": "westus", "kind": "StorageV2", "sku": {"name": "Standard_GRS"}, "properties": {"accessTier": "Cool", "supportsHttpsTrafficOnly": True}},
    ],
    "database_discovery": [
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Sql/servers/sql-prod-01", "name": "sql-prod-01", "type": "Microsoft.Sql/servers", "location": "eastus", "properties": {"administratorLogin": "sqladmin", "version": "12.0", "state": "Ready", "fullyQualifiedDomainName": "sql-prod-01.database.windows.net"}},
    ],
    "networking_discovery": [
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod", "name": "vnet-prod", "type": "Microsoft.Network/virtualNetworks", "location": "eastus", "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}, "subnets": [{"name": "web-subnet", "properties": {"addressPrefix": "10.0.1.0/24"}}, {"name": "api-subnet", "properties": {"addressPrefix": "10.0.2.0/24"}}]}},
    ],
    "appservice_discovery": [
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Web/sites/app-frontend", "name": "app-frontend", "type": "Microsoft.Web/sites", "location": "eastus", "kind": "app,linux", "properties": {"state": "Running", "defaultHostName": "app-frontend.azurewebsites.net", "httpsOnly": True}},
        {"id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Web/sites/app-api", "name": "app-api", "type": "Microsoft.Web/sites", "location": "eastus", "kind": "app,linux", "properties": {"state": "Running", "defaultHostName": "app-api.azurewebsites.net", "httpsOnly": True}},
    ],
}


def stub_mcp_result(tool_id: str, args: Dict) -> Dict:
    """Return stub MCP result with category-specific mock resources."""
    now = datetime.datetime.utcnow().isoformat()
    resources = STUB_RESOURCES.get(tool_id, [])
    return {
        "status": "success",
        "result": {
            "summary": f"{tool_id}: found {len(resources)} resources (stub)",
            "counts": {"resources": len(resources)},
            "resources": resources,
            "timestamp": now,
            "scope": {"tenant_id": args.get("tenant_id"), "subscription_id": args.get("subscription_id")},
        },
        "metadata": {"mode": "stub", "tool_id": tool_id, "executed_at": now},
    }


def call_mcp_execute(
    tool_id: str,
    args: Dict,
    trace_id: str,
    correlation_id: str,
    session_id: str,
    agent_step: int,
    attempt: int,
    access_token: Optional[str] = None,
) -> Dict:
    """Execute a single tool call via MCP server with correlation headers."""
    # Use stub mode unless we have a real access token
    use_stub = settings.mcp_stub_mode and not access_token
    if use_stub:
        return stub_mcp_result(tool_id, args)
    if not settings.mcp_base_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MCP base URL not configured.")
    url = settings.mcp_base_url.rstrip("/") + settings.mcp_execute_path
    payload = {
        "session_id": session_id,
        "trace_id": trace_id,
        "tool_id": tool_id,
        "args": args,
        "connection_id": args.get("connection_id", ""),
        "agent_step": agent_step,
        "attempt": attempt,
        "correlation_id": correlation_id,
    }
    # Pass access token to MCP server for token injection
    if access_token:
        payload["access_token"] = access_token
    try:
        with httpx.Client(timeout=settings.mcp_timeout_seconds) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "X-Trace-ID": trace_id,
                    "X-Correlation-ID": correlation_id,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "mcp_execute_failed trace_id=%s correlation_id=%s tool_id=%s status=%s body=%s",
            trace_id,
            correlation_id,
            tool_id,
            exc.response.status_code,
            exc.response.text,
        )
        status_code = exc.response.status_code
        raise HTTPException(status_code=status_code, detail="MCP execution failed.")
    except httpx.RequestError as exc:
        logger.error(
            "mcp_execute_error trace_id=%s correlation_id=%s tool_id=%s error=%s",
            trace_id,
            correlation_id,
            tool_id,
            exc,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to reach MCP.")


def execute_tool_with_retries(
    tool_id: str,
    args: Dict,
    trace_id: str,
    correlation_id: str,
    session_id: str,
    max_retries: int,
    access_token: Optional[str] = None,
) -> Dict:
    """Execute tool with exponential backoff retry logic for transient errors."""
    attempt = 1
    while attempt <= max_retries + 1:
        try:
            return call_mcp_execute(
                tool_id, args, trace_id, correlation_id, session_id,
                agent_step=attempt, attempt=attempt, access_token=access_token,
            )
        except HTTPException as exc:
            if exc.status_code in {401, 403, 404}:
                raise
            if attempt > max_retries:
                raise
            time.sleep(min(2 ** attempt, 5))
            attempt += 1
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MCP execution did not return.")

"""MCP client for tool execution with retry logic."""
import datetime
import logging
import time
from typing import Dict

import httpx
from fastapi import HTTPException, status

from config import settings

logger = logging.getLogger("agent-orchestrator.mcp.client")


def stub_mcp_result(tool_id: str, args: Dict) -> Dict:
    """Return stub MCP result for local development without MCP server."""
    now = datetime.datetime.utcnow().isoformat()
    return {
        "status": "success",
        "result": {
            "summary": f"{tool_id} executed in stub mode",
            "counts": {"resources": 1},
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
) -> Dict:
    """Execute a single tool call via MCP server with correlation headers."""
    if settings.mcp_stub_mode:
        return stub_mcp_result(tool_id, args)
    if not settings.mcp_base_url:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MCP base URL not configured.")
    url = settings.mcp_base_url.rstrip("/") + settings.mcp_execute_path
    payload = {
        "session_id": session_id,
        "trace_id": trace_id,
        "tool_id": tool_id,
        "args": args,
        "agent_step": agent_step,
        "attempt": attempt,
        "correlation_id": correlation_id,
    }
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
) -> Dict:
    """Execute tool with exponential backoff retry logic for transient errors."""
    attempt = 1
    while attempt <= max_retries + 1:
        try:
            return call_mcp_execute(tool_id, args, trace_id, correlation_id, session_id, agent_step=attempt, attempt=attempt)
        except HTTPException as exc:
            if exc.status_code in {401, 403, 404}:
                raise
            if attempt > max_retries:
                raise
            time.sleep(min(2 ** attempt, 5))
            attempt += 1
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="MCP execution did not return.")

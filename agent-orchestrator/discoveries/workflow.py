"""Discovery workflow execution with 4-stage pattern (validate → tier → infer → persist)."""
import datetime
import logging
import uuid
from typing import Dict, List, Optional

from fastapi import HTTPException, Request, status

from config import settings
from models import PlanStep

logger = logging.getLogger("agent-orchestrator.discoveries.workflow")

# Discovery tier priority for RBAC enforcement
TIER_PRIORITY = {"inventory": 1, "cost": 2, "security": 3}

# Tool schemas mapping
TOOL_SCHEMAS = {
    "inventory_discovery": {
        "description": "Read-only inventory of Azure resources for a given subscription/tenant.",
        "inputs": ["connection_id", "tenant_id", "subscription_id", "tier=inventory", "correlation_id", "session_id"],
        "outputs": ["resource_summary", "counts", "timestamp"],
    },
    "cost_discovery": {
        "description": "Retrieve Azure cost/usage data for an authorized scope.",
        "inputs": ["connection_id", "tenant_id", "subscription_id", "tier=cost", "correlation_id", "session_id"],
        "outputs": ["cost_summary", "currency", "timeframe", "timestamp"],
    },
    "security_discovery": {
        "description": "Fetch security posture/policy/defender signals for an authorized scope.",
        "inputs": ["connection_id", "tenant_id", "subscription_id", "tier=security", "correlation_id", "session_id"],
        "outputs": ["security_findings", "counts", "timestamp"],
    },
}


def validate_connection_scope(connection: Dict, tenant_id: Optional[str], subscription_id: Optional[str]) -> None:
    """Validate that the connection authorizes the requested scope."""
    if subscription_id and subscription_id not in connection.get("subscription_ids", []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription not authorized for this connection.",
        )
    if tenant_id and tenant_id != connection.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant not authorized for this connection.",
        )


def tool_for_tier(tier: str) -> str:
    """Map discovery tier to tool ID."""
    mapping = {"inventory": "inventory_discovery", "cost": "cost_discovery", "security": "security_discovery"}
    tool_id = mapping.get(tier)
    if not tool_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported discovery tier.")
    return tool_id


def enforce_rbac_and_policy(connection: Dict, tier: str) -> None:
    """Enforce RBAC tier restrictions (inventory < cost < security)."""
    conn_tier = connection.get("rbac_tier") or "inventory"
    if TIER_PRIORITY.get(tier, 0) > TIER_PRIORITY.get(conn_tier, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Connection RBAC tier '{conn_tier}' does not allow '{tier}' discovery.",
        )


def build_plan_template(tier: str) -> List[PlanStep]:
    """Build 4-stage discovery plan template."""
    return [
        PlanStep(name="validate", status="completed"),
        PlanStep(name=tier, status="pending"),
        PlanStep(name="infer", status="pending"),
        PlanStep(name="persist", status="pending"),
    ]


def summarize_tool_result(tier: str, result: Dict) -> Dict:
    """Summarize tool execution result for infer stage."""
    summary = result.get("summary") or f"{tier} discovery completed"
    counts = result.get("counts") or {}
    timestamp = result.get("timestamp") or datetime.datetime.utcnow().isoformat()
    return {"summary": summary, "counts": counts, "timestamp": timestamp}


def run_discovery_workflow(
    request: Request,
    connection: Dict,
    tenant_id: Optional[str],
    subscription_id: Optional[str],
    tier: str,
    session_id: str,
    discovery_repo,
    execute_tool_with_retries_fn,
) -> Dict:
    """
    Execute 4-stage discovery workflow: validate → tier → infer → persist.

    Args:
        request: FastAPI request for correlation ID
        connection: Connection document with auth credentials
        tenant_id: Optional Azure tenant ID
        subscription_id: Optional Azure subscription ID
        tier: Discovery tier (inventory, cost, security)
        session_id: Session ID for tracing
        discovery_repo: Discovery repository for persistence
        execute_tool_with_retries_fn: MCP client function for tool execution

    Returns:
        Dict with discovery, plan, trace_id, correlation_id, final_response, session_id
    """
    enforce_rbac_and_policy(connection, tier)
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    plan = build_plan_template(tier)

    now = datetime.datetime.utcnow().isoformat()
    discovery_doc = {
        "discovery_id": str(uuid.uuid4()),
        "connection_id": connection["connection_id"],
        "tenant_id": tenant_id or connection.get("tenant_id"),
        "subscription_id": subscription_id,
        "tier": tier,
        "stage": "validate",
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "session_id": session_id,
    }
    saved = discovery_repo.create(discovery_doc)

    # Execute discovery tool
    tool_id = tool_for_tier(tier)
    args = {
        "connection_id": connection["connection_id"],
        "tenant_id": tenant_id or connection.get("tenant_id"),
        "subscription_id": subscription_id,
        "tier": tier,
        "correlation_id": correlation_id,
        "session_id": session_id,
    }

    saved["stage"] = tier
    saved["status"] = "in_progress"
    saved["updated_at"] = datetime.datetime.utcnow().isoformat()
    saved = discovery_repo.update(saved)

    tool_result = execute_tool_with_retries_fn(
        tool_id,
        args,
        trace_id=trace_id,
        correlation_id=correlation_id,
        session_id=session_id,
        max_retries=settings.max_total_retries,
    )

    # Update plan with tool execution result
    plan[1].status = "completed"
    plan[1].detail = {"tool_id": tool_id, "status": tool_result.get("status"), "metadata": tool_result.get("metadata")}

    # Infer stage: summarize results
    infer_payload = summarize_tool_result(tier, tool_result.get("result", {}))
    plan[2].status = "completed"
    plan[2].detail = {"summary": infer_payload.get("summary"), "counts": infer_payload.get("counts")}

    saved["stage"] = "infer"
    saved["results"] = {"tool_result": tool_result.get("result"), "summary": infer_payload}
    saved["updated_at"] = datetime.datetime.utcnow().isoformat()
    saved = discovery_repo.update(saved)

    # Persist stage: finalize discovery
    saved["stage"] = "persist"
    saved["status"] = "completed"
    saved["updated_at"] = datetime.datetime.utcnow().isoformat()
    saved = discovery_repo.update(saved)

    plan[3].status = "completed"
    plan[3].detail = {"discovery_id": saved["discovery_id"]}

    logger.info(
        "discovery_complete trace_id=%s correlation_id=%s session_id=%s connection_id=%s tier=%s",
        trace_id,
        correlation_id,
        session_id,
        connection["connection_id"],
        tier,
    )

    return {
        "discovery": saved,
        "plan": plan,
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "final_response": infer_payload.get("summary"),
        "session_id": session_id,
    }

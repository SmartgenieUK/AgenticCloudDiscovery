"""Multi-agent discovery workflow: inventory → service category agents → aggregate → persist."""
import datetime
import logging
import uuid
from typing import Callable, Dict, List, Optional

from fastapi import Request

from config import settings
from models import PlanStep

logger = logging.getLogger("agent-orchestrator.discoveries.agent_workflow")

# Service category registry: maps category keys to tool IDs and Azure provider namespaces
SERVICE_CATEGORIES = {
    "compute": {
        "tool_id": "compute_discovery",
        "label": "Compute",
        "provider_namespaces": ["Microsoft.Compute"],
    },
    "storage": {
        "tool_id": "storage_discovery",
        "label": "Storage",
        "provider_namespaces": ["Microsoft.Storage"],
    },
    "databases": {
        "tool_id": "database_discovery",
        "label": "Databases",
        "provider_namespaces": ["Microsoft.Sql", "Microsoft.DBforMySQL", "Microsoft.DBforPostgreSQL"],
    },
    "networking": {
        "tool_id": "networking_discovery",
        "label": "Networking",
        "provider_namespaces": ["Microsoft.Network"],
    },
    "app_services": {
        "tool_id": "appservice_discovery",
        "label": "App Services",
        "provider_namespaces": ["Microsoft.Web"],
    },
}


def match_providers_to_categories(inventory_resources: List[Dict]) -> Dict[str, bool]:
    """Determine which service categories have matching resources in the inventory."""
    found_namespaces = set()
    for resource in inventory_resources:
        resource_type = resource.get("type", "")
        namespace = resource_type.split("/")[0] if "/" in resource_type else resource_type
        found_namespaces.add(namespace)

    category_matches = {}
    for cat_key, cat_def in SERVICE_CATEGORIES.items():
        has_match = any(ns in found_namespaces for ns in cat_def["provider_namespaces"])
        category_matches[cat_key] = has_match
    return category_matches


def build_agent_plan(matched_categories: Dict[str, bool]) -> List[PlanStep]:
    """Build a dynamic plan with steps for each matched service category."""
    steps = [
        PlanStep(name="validate", status="completed", label="Validate"),
        PlanStep(name="inventory", status="pending", label="Inventory Scan"),
    ]
    for cat_key, matched in matched_categories.items():
        label = SERVICE_CATEGORIES[cat_key]["label"]
        steps.append(PlanStep(
            name=cat_key,
            status="pending" if matched else "skipped",
            detail={"label": label, "matched": matched},
            label=label,
        ))
    steps.append(PlanStep(name="aggregate", status="pending", label="Aggregate"))
    steps.append(PlanStep(name="persist", status="pending", label="Persist"))
    return steps


def run_agent_discovery_workflow(
    request: Request,
    connection: Dict,
    tenant_id: Optional[str],
    subscription_id: Optional[str],
    session_id: str,
    discovery_repo,
    execute_tool_with_retries_fn: Callable,
    categories: Optional[List[str]] = None,
) -> Dict:
    """
    Execute multi-agent discovery: validate → inventory → service agents → aggregate → persist.

    Args:
        request: FastAPI request for correlation ID
        connection: Connection document with auth credentials
        tenant_id: Optional Azure tenant ID
        subscription_id: Optional Azure subscription ID
        session_id: Session ID for tracing
        discovery_repo: Discovery repository for persistence
        execute_tool_with_retries_fn: MCP client function for tool execution
        categories: Optional filter to restrict which service categories to scan

    Returns:
        Dict with discovery, plan, trace_id, correlation_id, final_response, session_id
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    access_token = connection.get("access_token")
    resolved_tenant = tenant_id or connection.get("tenant_id")
    now = datetime.datetime.utcnow().isoformat()

    # Create discovery document
    discovery_doc = {
        "discovery_id": str(uuid.uuid4()),
        "connection_id": connection["connection_id"],
        "tenant_id": resolved_tenant,
        "subscription_id": subscription_id,
        "stage": "validate",
        "status": "in_progress",
        "snapshot_timestamp": now,
        "created_at": now,
        "updated_at": now,
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "session_id": session_id,
    }
    saved = discovery_repo.create(discovery_doc)

    base_args = {
        "connection_id": connection["connection_id"],
        "tenant_id": resolved_tenant,
        "subscription_id": subscription_id,
        "correlation_id": correlation_id,
        "session_id": session_id,
    }

    # --- Stage 1: Inventory ---
    saved["stage"] = "inventory"
    saved["updated_at"] = datetime.datetime.utcnow().isoformat()
    saved = discovery_repo.update(saved)

    logger.info("agent_discovery inventory_start trace_id=%s", trace_id)
    inventory_result = execute_tool_with_retries_fn(
        "inventory_discovery",
        base_args,
        trace_id=trace_id,
        correlation_id=correlation_id,
        session_id=session_id,
        max_retries=settings.max_total_retries,
        access_token=access_token,
    )
    inventory_resources = inventory_result.get("result", {}).get("resources", [])
    logger.info("agent_discovery inventory_done resources=%d trace_id=%s", len(inventory_resources), trace_id)

    # --- Stage 2: Match categories ---
    all_matches = match_providers_to_categories(inventory_resources)

    # Apply optional category filter
    if categories:
        all_matches = {k: v for k, v in all_matches.items() if k in categories}
    else:
        # Include all categories (even unmatched ones show as skipped)
        pass

    plan = build_agent_plan(all_matches)
    # Mark inventory as completed
    plan[1].status = "completed"
    providers_found = list(set(
        r.get("type", "").split("/")[0] for r in inventory_resources if "/" in r.get("type", "")
    ))
    plan[1].detail = {"total_resources": len(inventory_resources), "providers_found": providers_found}

    # --- Stage 3: Dispatch service category agents ---
    category_results = {}
    plan_index = 2  # first category step in plan

    for cat_key, matched in all_matches.items():
        if not matched:
            category_results[cat_key] = {"status": "skipped", "resource_count": 0, "resources": []}
            plan[plan_index].status = "skipped"
            plan_index += 1
            continue

        plan[plan_index].status = "in_progress"
        saved["stage"] = cat_key
        saved["updated_at"] = datetime.datetime.utcnow().isoformat()
        saved = discovery_repo.update(saved)

        tool_id = SERVICE_CATEGORIES[cat_key]["tool_id"]
        logger.info("agent_discovery dispatch category=%s tool=%s trace_id=%s", cat_key, tool_id, trace_id)

        try:
            cat_result = execute_tool_with_retries_fn(
                tool_id,
                base_args,
                trace_id=trace_id,
                correlation_id=correlation_id,
                session_id=session_id,
                max_retries=settings.max_total_retries,
                access_token=access_token,
            )
            resources = cat_result.get("result", {}).get("resources", [])
            category_results[cat_key] = {
                "status": "completed",
                "resource_count": len(resources),
                "resources": resources,
                "summary": cat_result.get("result", {}).get("summary", ""),
            }
            plan[plan_index].status = "completed"
            plan[plan_index].detail = {
                "label": SERVICE_CATEGORIES[cat_key]["label"],
                "resource_count": len(resources),
            }
            logger.info("agent_discovery category_done category=%s resources=%d trace_id=%s", cat_key, len(resources), trace_id)
        except Exception as exc:
            category_results[cat_key] = {"status": "failed", "error": str(exc), "resource_count": 0, "resources": []}
            plan[plan_index].status = "failed"
            plan[plan_index].detail = {"label": SERVICE_CATEGORIES[cat_key]["label"], "error": str(exc)}
            logger.error("agent_discovery category_failed category=%s error=%s trace_id=%s", cat_key, exc, trace_id)

        plan_index += 1

    # --- Stage 4: Aggregate ---
    aggregate_index = plan_index
    persist_index = plan_index + 1

    total_discovered = sum(cr["resource_count"] for cr in category_results.values())
    active_categories = [k for k, v in category_results.items() if v["status"] == "completed"]
    summary = f"Discovered {total_discovered} resources across {len(active_categories)} service categories."

    saved["results"] = {
        "inventory": {
            "total_resources": len(inventory_resources),
            "providers_found": providers_found,
            "resources": inventory_resources,
        },
        "categories": category_results,
        "summary": summary,
    }

    plan[aggregate_index].status = "completed"
    plan[aggregate_index].detail = {"total_resources": total_discovered, "categories_scanned": len(active_categories)}

    # --- Stage 5: Persist ---
    saved["stage"] = "persist"
    saved["status"] = "completed"
    saved["updated_at"] = datetime.datetime.utcnow().isoformat()
    saved = discovery_repo.update(saved)

    plan[persist_index].status = "completed"
    plan[persist_index].detail = {"discovery_id": saved["discovery_id"]}

    logger.info(
        "agent_discovery_complete trace_id=%s correlation_id=%s session_id=%s categories=%s total=%d",
        trace_id, correlation_id, session_id, ",".join(active_categories), total_discovered,
    )

    return {
        "discovery": saved,
        "plan": plan,
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "final_response": summary,
        "session_id": session_id,
    }

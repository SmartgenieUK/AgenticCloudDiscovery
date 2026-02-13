"""Multi-agent discovery workflow: inventory → service category agents → aggregate → persist.

Includes both the original category-based workflow and the new layered discovery engine.
"""
import datetime
import logging
import uuid
from typing import Callable, Dict, List, Optional

from fastapi import Request

from config import settings
from models import LayerPlan, LayerPlanStep, PlanStep

from .layers import LAYER_REGISTRY, resolve_layer_dependencies

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


# ====================== Layered Discovery Workflow ======================

# Friendly display labels for Azure provider namespaces.
# Any namespace not listed here will be auto-labelled from its name (e.g. "Microsoft.Cdn" → "Cdn").
_NAMESPACE_LABELS = {
    "Microsoft.Compute": "Compute",
    "Microsoft.ContainerRegistry": "Container Registry",
    "Microsoft.ContainerInstance": "Container Instances",
    "Microsoft.ContainerService": "Kubernetes (AKS)",
    "Microsoft.App": "Container Apps",
    "Microsoft.Storage": "Storage",
    "Microsoft.Sql": "SQL Database",
    "Microsoft.DBforMySQL": "MySQL",
    "Microsoft.DBforPostgreSQL": "PostgreSQL",
    "Microsoft.DBforMariaDB": "MariaDB",
    "Microsoft.DocumentDB": "Cosmos DB",
    "Microsoft.Cache": "Redis Cache",
    "Microsoft.Network": "Networking",
    "Microsoft.Cdn": "CDN",
    "Microsoft.Web": "App Service",
    "Microsoft.ApiManagement": "API Management",
    "Microsoft.KeyVault": "Key Vault",
    "Microsoft.ManagedIdentity": "Managed Identity",
    "Microsoft.Authorization": "Authorization",
    "Microsoft.Insights": "Application Insights",
    "Microsoft.OperationalInsights": "Log Analytics",
    "Microsoft.Monitor": "Monitor",
    "Microsoft.AlertsManagement": "Alerts",
    "Microsoft.SignalRService": "SignalR",
    "Microsoft.ServiceFabric": "Service Fabric",
    "Microsoft.Batch": "Batch",
    "Microsoft.Relay": "Relay",
    "Microsoft.StorageSync": "Storage Sync",
}


# Friendly labels for discovery tools shown in the UI stepper.
_TOOL_LABELS = {
    "rg_inventory_discovery": "Resource Graph: Inventory",
    "rg_topology_discovery": "Resource Graph: Topology",
    "rg_identity_discovery": "Resource Graph: Identity & Roles",
    "rg_policy_discovery": "Resource Graph: Policy Assignments",
    "inventory_discovery": "Inventory Scan",
}


def stub_layer_analysis(layer_id: str, collection_results: Dict) -> Dict:
    """Placeholder for AI analysis. Returns stub insights."""
    total = sum(cr.get("resource_count", 0) for cr in collection_results.values())
    return {
        "status": "stub",
        "insights": [],
        "summary": f"AI analysis for {layer_id} pending. {total} resources available for analysis.",
        "model": None,
        "tokens_used": 0,
    }


def _extract_inventory_compat(inventory_layer_result: Dict) -> Dict:
    """Extract old-style inventory from Layer 1 results for backward compatibility.

    Works with both Resource Graph tools (rg_inventory_discovery) and legacy tools.
    """
    collection = inventory_layer_result.get("collection", {})
    # Try Resource Graph tool first, fall back to legacy
    inv_tool = collection.get("rg_inventory_discovery") or collection.get("inventory_discovery") or {}
    all_resources = inv_tool.get("resources", [])
    providers_found = list(set(
        r.get("type", "").split("/")[0]
        for r in all_resources
        if "/" in r.get("type", "")
    ))
    return {
        "total_resources": len(all_resources),
        "providers_found": providers_found,
        "resources": all_resources,
    }


# Build case-insensitive lookup for namespace labels
_NAMESPACE_LABELS_LOWER = {k.lower(): v for k, v in _NAMESPACE_LABELS.items()}


def _namespace_label(namespace: str) -> str:
    """Return a friendly display label for an Azure provider namespace (case-insensitive)."""
    label = _NAMESPACE_LABELS_LOWER.get(namespace.lower())
    if label:
        return label
    # Strip "Microsoft." prefix for unknown namespaces
    ns = namespace if namespace[0:1].isupper() else namespace.title()
    return ns.replace("Microsoft.", "") if ns.lower().startswith("microsoft.") else ns


def _extract_categories_compat(inventory_layer_result: Dict) -> Dict:
    """Group inventory resources by Azure provider namespace.

    Categories are fully dynamic — only namespaces that actually appear in the
    discovered resources are returned. No hardcoded category list.
    """
    collection = inventory_layer_result.get("collection", {})
    inv_tool = collection.get("rg_inventory_discovery") or collection.get("inventory_discovery") or {}
    all_resources = inv_tool.get("resources", [])

    # Group resources by namespace
    categories: Dict[str, Dict] = {}
    for resource in all_resources:
        rtype = resource.get("type", "")
        namespace = rtype.split("/")[0] if "/" in rtype else "unknown"
        if namespace not in categories:
            categories[namespace] = {
                "status": "completed",
                "label": _namespace_label(namespace),
                "resource_count": 0,
                "resources": [],
            }
        categories[namespace]["resources"].append(resource)
        categories[namespace]["resource_count"] += 1

    # Log category breakdown
    breakdown = {v["label"]: v["resource_count"] for v in categories.values()}
    logger.info("category_breakdown total=%d categories=%s", len(all_resources), breakdown)

    return categories


def _flatten_layer_plans(layer_plans: List[LayerPlan]) -> List[PlanStep]:
    """Flatten hierarchical layer plans into a flat PlanStep list for backward compat."""
    flat = [PlanStep(name="validate", status="completed", label="Validate")]
    for lp in layer_plans:
        flat.append(PlanStep(
            name=lp.layer_id,
            status=lp.status,
            label=lp.label,
            detail=lp.detail,
        ))
    flat.append(PlanStep(name="aggregate", status="completed", label="Aggregate"))
    flat.append(PlanStep(name="persist", status="completed", label="Persist"))
    return flat


def run_layered_discovery_workflow(
    request: Request,
    connection: Dict,
    tenant_id: Optional[str],
    subscription_id: Optional[str],
    session_id: str,
    discovery_repo,
    execute_tool_with_retries_fn: Callable,
    layer_ids: List[str],
) -> Dict:
    """Execute layered discovery: resolve deps → for each layer: collect → analyze → aggregate → persist.

    Args:
        request: FastAPI request for correlation ID
        connection: Connection document with auth credentials
        tenant_id: Optional Azure tenant ID
        subscription_id: Optional Azure subscription ID
        session_id: Session ID for tracing
        discovery_repo: Discovery repository for persistence
        execute_tool_with_retries_fn: MCP client function for tool execution
        layer_ids: List of layer IDs to run (dependencies auto-resolved)

    Returns:
        Dict with discovery, plan, layer_plan, trace_id, correlation_id, final_response, session_id
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    access_token = connection.get("access_token")
    resolved_tenant = tenant_id or connection.get("tenant_id")
    now = datetime.datetime.utcnow().isoformat()

    # 1. Resolve dependencies
    resolved_ids = resolve_layer_dependencies(layer_ids)
    user_requested = set(layer_ids)

    logger.info(
        "layered_discovery_start layers=%s resolved=%s trace_id=%s",
        ",".join(layer_ids), ",".join(resolved_ids), trace_id,
    )

    # 2. Build hierarchical plan
    layer_plans: List[LayerPlan] = []
    for lid in resolved_ids:
        layer_def = LAYER_REGISTRY[lid]
        auto = lid not in user_requested
        tool_steps = [
            LayerPlanStep(
                name=tid,
                status="pending",
                label=_TOOL_LABELS.get(tid, tid.replace("_discovery", "").replace("_", " ").title()),
            )
            for tid in layer_def.collection_tool_ids
        ]
        analysis_step = LayerPlanStep(
            name=f"{lid}_analysis",
            status="pending",
            label=f"{layer_def.label} Analysis",
        )
        lp = LayerPlan(
            layer_id=lid,
            layer_number=layer_def.layer_number,
            label=layer_def.label,
            status="pending",
            auto_resolved=auto,
            steps=tool_steps,
            analysis=analysis_step,
        )
        layer_plans.append(lp)

    # 3. Create discovery document
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
        "subscription_ids": connection.get("subscription_ids", [subscription_id] if subscription_id else []),
        "correlation_id": correlation_id,
        "session_id": session_id,
    }

    # 4. Execute each layer — all layers use the same sequential tool execution
    all_layer_results: Dict[str, Dict] = {}

    for lp in layer_plans:
        layer_def = LAYER_REGISTRY[lp.layer_id]
        lp.status = "in_progress"
        saved["stage"] = lp.layer_id
        saved["updated_at"] = datetime.datetime.utcnow().isoformat()
        saved = discovery_repo.update(saved)

        logger.info("layered_discovery layer_start layer=%s trace_id=%s", lp.layer_id, trace_id)

        collection_results: Dict[str, Dict] = {}

        # All layers: run tools sequentially
        for tool_step in lp.steps:
            tool_step.status = "in_progress"
            try:
                result = execute_tool_with_retries_fn(
                    tool_step.name, base_args,
                    trace_id=trace_id, correlation_id=correlation_id,
                    session_id=session_id, max_retries=settings.max_total_retries,
                    access_token=access_token,
                )
                mcp_status = result.get("status", "success")
                tool_result = result.get("result") or {}
                resources = tool_result.get("resources", [])
                kql_query = tool_result.get("kql_query")
                if kql_query:
                    logger.info("KQL [%s]: %s", tool_step.name, kql_query)

                if mcp_status == "failure":
                    error_msg = result.get("error", {}).get("message", "MCP execution failed")
                    logger.warning(
                        "tool_failed tool=%s error=%s kql=%s",
                        tool_step.name, error_msg, "yes" if kql_query else "no",
                    )
                    collection_results[tool_step.name] = {
                        "status": "failed", "error": error_msg,
                        "resource_count": 0, "resources": [],
                    }
                    tool_step.status = "failed"
                    tool_step.detail = {"error": error_msg}
                    if kql_query:
                        tool_step.detail["kql_query"] = kql_query
                else:
                    logger.info(
                        "tool_result tool=%s resources=%d kql=%s",
                        tool_step.name, len(resources), "yes" if kql_query else "no",
                    )
                    collection_results[tool_step.name] = {
                        "status": "completed",
                        "resource_count": len(resources),
                        "resources": resources,
                    }
                    tool_step.status = "completed"
                    tool_step.detail = {"resource_count": len(resources)}
                    if kql_query:
                        tool_step.detail["kql_query"] = kql_query
            except Exception as exc:
                collection_results[tool_step.name] = {
                    "status": "failed", "error": str(exc),
                    "resource_count": 0, "resources": [],
                }
                tool_step.status = "failed"
                tool_step.detail = {"error": str(exc)}

        # Analysis phase (stub)
        analysis_result = stub_layer_analysis(lp.layer_id, collection_results)
        if lp.analysis:
            lp.analysis.status = "completed"
            lp.analysis.detail = {"mode": "stub"}

        # Accumulate layer results
        total = sum(cr["resource_count"] for cr in collection_results.values())
        all_layer_results[lp.layer_id] = {
            "status": "completed",
            "collection": collection_results,
            "analysis": analysis_result,
            "summary": f"Layer {lp.label}: {total} resources collected.",
        }
        lp.status = "completed"
        lp.detail = {"total_resources": total}

        logger.info(
            "layered_discovery layer_done layer=%s resources=%d trace_id=%s",
            lp.layer_id, total, trace_id,
        )

    # 5. Aggregate
    results: Dict = {"layers": all_layer_results}

    # Backward-compat: extract old-style inventory/categories from Layer 1
    if "inventory" in all_layer_results:
        results["inventory"] = _extract_inventory_compat(all_layer_results["inventory"])
        results["categories"] = _extract_categories_compat(all_layer_results["inventory"])

    # Build summary
    layer_summaries = []
    for lid, lr in all_layer_results.items():
        layer_summaries.append(LAYER_REGISTRY[lid].label)
    total_all = sum(
        lr.get("collection", {}).get(tid, {}).get("resource_count", 0)
        for lr in all_layer_results.values()
        for tid in lr.get("collection", {})
    )
    results["summary"] = f"Discovered {total_all} resources across {len(all_layer_results)} layers: {', '.join(layer_summaries)}."

    # Flatten plans for backward compat
    flat_plan = _flatten_layer_plans(layer_plans)

    # 6. Persist
    saved["results"] = results
    saved["stage"] = "persist"
    saved["status"] = "completed"
    saved["updated_at"] = datetime.datetime.utcnow().isoformat()
    saved = discovery_repo.update(saved)

    logger.info(
        "layered_discovery_complete trace_id=%s correlation_id=%s session_id=%s layers=%s total=%d",
        trace_id, correlation_id, session_id, ",".join(resolved_ids), total_all,
    )

    return {
        "discovery": saved,
        "plan": flat_plan,
        "layer_plan": [lp.dict() for lp in layer_plans],
        "trace_id": trace_id,
        "correlation_id": correlation_id,
        "final_response": results["summary"],
        "session_id": session_id,
    }

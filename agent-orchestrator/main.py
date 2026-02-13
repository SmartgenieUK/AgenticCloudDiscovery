import datetime
import logging
import os
import uuid
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

try:
    from azure.cosmos import CosmosClient, PartitionKey, exceptions as cosmos_exceptions
except ImportError:  # pragma: no cover - optional for local dev without Cosmos
    CosmosClient = None  # type: ignore
    PartitionKey = None  # type: ignore
    cosmos_exceptions = None  # type: ignore

# Import settings from config module
from config import settings

# Import models
from models import (
    UserProfile,
    CreateConnectionRequest,
    Connection,
    DiscoveryRequest,
    Discovery,
    ChatRequest,
    ChatResponse,
    sanitize_user,
    sanitize_connection,
)

# Import repository modules
from users import UserRepository, get_repository
from connections import ConnectionRepository, get_connection_repository
from discoveries import (
    DiscoveryRepository,
    get_discovery_repository,
    TIER_PRIORITY,
    TOOL_SCHEMAS,
    validate_connection_scope,
    run_discovery_workflow,
    SERVICE_CATEGORIES,
    run_agent_discovery_workflow,
    run_layered_discovery_workflow,
    LAYER_REGISTRY,
)

# Import auth module
from auth import auth_router, get_current_user
from auth.dependencies import set_repo_provider

# Import mcp client
from mcp import execute_tool_with_retries

# Import Azure auth
from azure_auth import acquire_sp_token, acquire_mi_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-orchestrator.main")


# Initialize repositories
repo_provider: UserRepository = get_repository()
connection_repo: ConnectionRepository = get_connection_repository()
discovery_repo: DiscoveryRepository = get_discovery_repository()

# Provide repository to auth module
set_repo_provider(repo_provider)


app = FastAPI(title="Agentic Orchestrator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


# Register auth router
app.include_router(auth_router)


# ==============================================================================
# System & Health Endpoints
# ==============================================================================


@app.get("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/mcp/tools")
def list_tools() -> Dict[str, Dict]:
    return TOOL_SCHEMAS


@app.get("/me", response_model=UserProfile)
def get_me(user: Dict = Depends(get_current_user)) -> UserProfile:
    return sanitize_user(user)


# ==============================================================================
# Connection Endpoints
# ==============================================================================


@app.post("/connections", response_model=Connection)
def create_connection(payload: CreateConnectionRequest, user: Dict = Depends(get_current_user)) -> Connection:
    now = datetime.datetime.utcnow().isoformat()
    access_token = payload.access_token
    token_expiry = payload.expires_at
    display_name = None

    # Acquire Azure AD token based on auth method
    if payload.provider == "service_principal" and payload.client_id and payload.client_secret:
        token_data = acquire_sp_token(payload.tenant_id, payload.client_id, payload.client_secret)
        access_token = token_data["access_token"]
        token_expiry = token_data["expires_on"]
        display_name = token_data.get("display_name")
    elif payload.provider == "managed_identity":
        token_data = acquire_mi_token(tenant_id=payload.tenant_id)
        access_token = token_data["access_token"]
        token_expiry = token_data["expires_on"]
        display_name = token_data.get("display_name")

    connection_doc = {
        "connection_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "tenant_id": payload.tenant_id,
        "subscription_ids": payload.subscription_ids,
        "provider": payload.provider,
        "status": "active",
        "expires_at": token_expiry,
        "access_token": access_token,  # stored server-side, never returned
        "client_id": payload.client_id,  # stored for token refresh
        "client_secret": payload.client_secret,  # stored for token refresh
        "display_name": display_name,
        "rbac_tier": payload.rbac_tier or "inventory",
        "created_at": now,
        "updated_at": now,
    }
    created = connection_repo.create(connection_doc)
    logger.info("connection_created user_id=%s tenant_id=%s provider=%s", user["user_id"], payload.tenant_id, payload.provider)
    return sanitize_connection(created)


@app.get("/connections", response_model=List[Connection])
def list_connections(user: Dict = Depends(get_current_user)) -> List[Connection]:
    items = connection_repo.list_for_user(user["user_id"])
    return [sanitize_connection(i) for i in items]


# ==============================================================================
# Discovery & Chat Endpoints
# ==============================================================================


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: Request,
    payload: ChatRequest,
    user: Dict = Depends(get_current_user),
) -> ChatResponse:
    connection = connection_repo.get_by_id(payload.connection_id)
    if not connection or connection.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid connection.")
    validate_connection_scope(connection, payload.tenant_id, payload.subscription_id)
    session_id = payload.session_id or str(uuid.uuid4())

    if payload.layers:
        # Layered discovery workflow
        outcome = run_layered_discovery_workflow(
            request=request,
            connection=connection,
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            session_id=session_id,
            discovery_repo=discovery_repo,
            execute_tool_with_retries_fn=execute_tool_with_retries,
            layer_ids=payload.layers,
        )
        response_text = outcome["final_response"] or "Layered discovery completed."
        logger.info(
            "chat_layered_discovery_complete trace_id=%s correlation_id=%s session_id=%s",
            outcome["trace_id"], outcome["correlation_id"], session_id,
        )
        return ChatResponse(
            session_id=session_id,
            trace_id=outcome["trace_id"],
            correlation_id=outcome["correlation_id"],
            plan=outcome["plan"],
            layer_plan=outcome.get("layer_plan"),
            discovery=Discovery(**outcome["discovery"]),
            final_response=response_text,
        )
    else:
        # Legacy category-based workflow
        outcome = run_agent_discovery_workflow(
            request=request,
            connection=connection,
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            session_id=session_id,
            discovery_repo=discovery_repo,
            execute_tool_with_retries_fn=execute_tool_with_retries,
            categories=payload.categories,
        )
        response_text = outcome["final_response"] or "Discovery completed."
        logger.info(
            "chat_discovery_complete trace_id=%s correlation_id=%s session_id=%s",
            outcome["trace_id"], outcome["correlation_id"], session_id,
        )
        return ChatResponse(
            session_id=session_id,
            trace_id=outcome["trace_id"],
            correlation_id=outcome["correlation_id"],
            plan=outcome["plan"],
            discovery=Discovery(**outcome["discovery"]),
            final_response=response_text,
        )


@app.post("/discoveries", response_model=Discovery)
def start_discovery(request: Request, payload: DiscoveryRequest, user: Dict = Depends(get_current_user)) -> Discovery:
    connection = connection_repo.get_by_id(payload.connection_id)
    if not connection or connection.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid connection.")
    validate_connection_scope(connection, payload.tenant_id, payload.subscription_id)
    session_id = str(uuid.uuid4())

    if payload.layers:
        outcome = run_layered_discovery_workflow(
            request=request,
            connection=connection,
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            session_id=session_id,
            discovery_repo=discovery_repo,
            execute_tool_with_retries_fn=execute_tool_with_retries,
            layer_ids=payload.layers,
        )
    else:
        outcome = run_agent_discovery_workflow(
            request=request,
            connection=connection,
            tenant_id=payload.tenant_id,
            subscription_id=payload.subscription_id,
            session_id=session_id,
            discovery_repo=discovery_repo,
            execute_tool_with_retries_fn=execute_tool_with_retries,
            categories=payload.categories,
        )
    return Discovery(**outcome["discovery"])


@app.get("/layers")
def list_layers() -> List[Dict]:
    """Return available discovery layers with metadata."""
    return [
        {
            "layer_id": layer.layer_id,
            "layer_number": layer.layer_number,
            "label": layer.label,
            "description": layer.description,
            "depends_on": layer.depends_on,
            "enabled": layer.enabled,
        }
        for layer in sorted(LAYER_REGISTRY.values(), key=lambda x: x.layer_number)
    ]


# ==============================================================================
# Graph / Topology Endpoints
# ==============================================================================


@app.get("/discoveries/{discovery_id}")
def get_discovery(
    discovery_id: str,
    user: Dict = Depends(get_current_user),
) -> Discovery:
    """Get a specific discovery by ID."""
    doc = discovery_repo.get_by_id(discovery_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found.")
    # Verify the discovery belongs to the user's connection
    conn = connection_repo.get_by_id(doc.get("connection_id", ""))
    if not conn or conn.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found.")
    return Discovery(**doc)


@app.get("/discoveries/{discovery_id}/graph")
def get_discovery_graph(
    discovery_id: str,
    scope: Optional[str] = None,
    include_edges: str = "contains,network_link,assigned_to,governed_by",
    user: Dict = Depends(get_current_user),
) -> Dict:
    """Build and return graph representation of discovery results."""
    from graph import build_graph_from_discovery

    doc = discovery_repo.get_by_id(discovery_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found.")
    conn = connection_repo.get_by_id(doc.get("connection_id", ""))
    if not conn or conn.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery not found.")

    graph_data = build_graph_from_discovery(doc)

    # Filter edges by requested types
    edge_types = set(t.strip() for t in include_edges.split(",") if t.strip())
    if edge_types:
        graph_data.edges = [e for e in graph_data.edges if e.label in edge_types]

    return graph_data.dict()

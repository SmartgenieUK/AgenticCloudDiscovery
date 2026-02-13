"""Graph database operations using Cosmos DB Gremlin API."""
from .graph_builder import build_graph_from_discovery, parse_resource_id

# Gremlin-dependent imports are optional (require gremlin_python package)
try:
    from .gremlin_client import GremlinGraphClient, get_graph_client
    from .graph_sync import GraphSyncService
except ImportError:
    GremlinGraphClient = None  # type: ignore
    get_graph_client = None  # type: ignore
    GraphSyncService = None  # type: ignore

__all__ = [
    "GremlinGraphClient",
    "get_graph_client",
    "GraphSyncService",
    "build_graph_from_discovery",
    "parse_resource_id",
]

"""Connection repository implementations."""
import logging
from typing import Dict, List, Optional

try:
    from azure.cosmos import CosmosClient, PartitionKey
except ImportError:
    CosmosClient = None
    PartitionKey = None

from config import Settings, settings

logger = logging.getLogger("agent-orchestrator.connections")


class ConnectionRepository:
    """Abstract base class for connection repositories."""

    def get_by_id(self, connection_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def list_for_user(self, user_id: str) -> List[Dict]:
        raise NotImplementedError

    def create(self, doc: Dict) -> Dict:
        raise NotImplementedError


class CosmosConnectionRepository(ConnectionRepository):
    """Cosmos DB implementation of connection repository."""

    def __init__(self, settings: Settings) -> None:
        if CosmosClient is None:
            raise RuntimeError("azure-cosmos is not installed.")
        self.client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        self.database = self.client.create_database_if_not_exists(id=settings.cosmos_db)
        self.container = self.database.create_container_if_not_exists(
            id=settings.cosmos_connections_container,
            partition_key=PartitionKey(path="/connection_id"),
        )

    def get_by_id(self, connection_id: str) -> Optional[Dict]:
        try:
            return self.container.read_item(item=connection_id, partition_key=connection_id)
        except Exception:
            query = "SELECT * FROM c WHERE c.connection_id = @cid"
            items = list(
                self.container.query_items(
                    query=query,
                    parameters=[{"name": "@cid", "value": connection_id}],
                    enable_cross_partition_query=True,
                )
            )
            return items[0] if items else None

    def list_for_user(self, user_id: str) -> List[Dict]:
        query = "SELECT * FROM c WHERE c.user_id = @uid"
        items = list(
            self.container.query_items(
                query=query,
                parameters=[{"name": "@uid", "value": user_id}],
                enable_cross_partition_query=True,
            )
        )
        return items

    def create(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("connection_id")
        return self.container.create_item(doc)


class InMemoryConnectionRepository(ConnectionRepository):
    """In-memory implementation of connection repository for testing."""

    def __init__(self) -> None:
        self.connections: Dict[str, Dict] = {}

    def get_by_id(self, connection_id: str) -> Optional[Dict]:
        return self.connections.get(connection_id)

    def list_for_user(self, user_id: str) -> List[Dict]:
        return [c for c in self.connections.values() if c["user_id"] == user_id]

    def create(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("connection_id")
        self.connections[doc["connection_id"]] = doc
        return doc


def get_connection_repository() -> ConnectionRepository:
    """Get connection repository instance (Cosmos or in-memory fallback)."""
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            logger.info("Using Cosmos DB for connections storage.")
            return CosmosConnectionRepository(settings)
        except Exception as exc:  # pragma: no cover - environment specific
            logger.warning("Falling back to in-memory connections store: %s", exc)
    logger.info("Using in-memory connections storage.")
    return InMemoryConnectionRepository()

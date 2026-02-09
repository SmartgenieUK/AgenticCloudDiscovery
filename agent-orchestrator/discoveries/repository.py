"""Discovery repository implementations."""
import logging
from typing import Dict, Optional

try:
    from azure.cosmos import CosmosClient, PartitionKey
except ImportError:
    CosmosClient = None
    PartitionKey = None

from config import Settings, settings

logger = logging.getLogger("agent-orchestrator.discoveries")


class DiscoveryRepository:
    """Abstract base class for discovery repositories."""

    def create(self, doc: Dict) -> Dict:
        raise NotImplementedError

    def get_by_id(self, discovery_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def update(self, doc: Dict) -> Dict:
        raise NotImplementedError


class CosmosDiscoveryRepository(DiscoveryRepository):
    """Cosmos DB implementation of discovery repository."""

    def __init__(self, settings: Settings) -> None:
        if CosmosClient is None:
            raise RuntimeError("azure-cosmos is not installed.")
        self.client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        self.database = self.client.create_database_if_not_exists(id=settings.cosmos_db)
        self.container = self.database.create_container_if_not_exists(
            id=settings.cosmos_discoveries_container,
            partition_key=PartitionKey(path="/discovery_id"),
        )

    def create(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("discovery_id")
        return self.container.create_item(doc)

    def get_by_id(self, discovery_id: str) -> Optional[Dict]:
        try:
            return self.container.read_item(item=discovery_id, partition_key=discovery_id)
        except Exception:
            return None

    def update(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("discovery_id")
        return self.container.upsert_item(doc)


class InMemoryDiscoveryRepository(DiscoveryRepository):
    """In-memory implementation of discovery repository for testing."""

    def __init__(self) -> None:
        self.discoveries: Dict[str, Dict] = {}

    def create(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("discovery_id")
        self.discoveries[doc["discovery_id"]] = doc
        return doc

    def get_by_id(self, discovery_id: str) -> Optional[Dict]:
        return self.discoveries.get(discovery_id)

    def update(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("discovery_id")
        self.discoveries[doc["discovery_id"]] = doc
        return doc


def get_discovery_repository() -> DiscoveryRepository:
    """Get discovery repository instance (Cosmos or in-memory fallback)."""
    if settings.cosmos_endpoint and settings.cosmos_key:
        logger.info("Using Cosmos DB for discoveries storage.")
        return CosmosDiscoveryRepository(settings)
    logger.info("Using in-memory discoveries storage.")
    return InMemoryDiscoveryRepository()

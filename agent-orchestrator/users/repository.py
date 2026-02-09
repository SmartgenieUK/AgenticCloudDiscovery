"""User repository implementations."""
import logging
from typing import Dict, Optional

try:
    from azure.cosmos import CosmosClient, PartitionKey
except ImportError:
    CosmosClient = None
    PartitionKey = None

from config import Settings, settings

logger = logging.getLogger("agent-orchestrator.users")


class UserRepository:
    """Abstract base class for user repositories."""

    def get_by_email(self, email: str) -> Optional[Dict]:
        raise NotImplementedError

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def create_user(self, doc: Dict) -> Dict:
        raise NotImplementedError

    def update_user(self, doc: Dict) -> Dict:
        raise NotImplementedError


class CosmosUserRepository(UserRepository):
    """Cosmos DB implementation of user repository."""

    def __init__(self, settings: Settings) -> None:
        if CosmosClient is None:
            raise RuntimeError("azure-cosmos is not installed.")
        self.client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        self.database = self.client.create_database_if_not_exists(id=settings.cosmos_db)
        self.container = self.database.create_container_if_not_exists(
            id=settings.cosmos_users_container,
            partition_key=PartitionKey(path="/user_id"),
        )

    def get_by_email(self, email: str) -> Optional[Dict]:
        query = "SELECT * FROM c WHERE c.email = @email"
        items = list(
            self.container.query_items(
                query=query,
                parameters=[{"name": "@email", "value": email}],
                enable_cross_partition_query=True,
            )
        )
        return items[0] if items else None

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        try:
            return self.container.read_item(item=user_id, partition_key=user_id)
        except Exception:
            # Fallback to query in case partition key differs or replicas lag
            query = "SELECT * FROM c WHERE c.user_id = @uid OR c.id = @uid"
            items = list(
                self.container.query_items(
                    query=query,
                    parameters=[{"name": "@uid", "value": user_id}],
                    enable_cross_partition_query=True,
                )
            )
            return items[0] if items else None

    def create_user(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("user_id")
        return self.container.create_item(doc)

    def update_user(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("user_id")
        return self.container.upsert_item(doc)


class InMemoryUserRepository(UserRepository):
    """In-memory implementation of user repository for testing."""

    def __init__(self) -> None:
        self.users: Dict[str, Dict] = {}

    def get_by_email(self, email: str) -> Optional[Dict]:
        return next((u for u in self.users.values() if u["email"] == email), None)

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        return self.users.get(user_id)

    def create_user(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("user_id")
        self.users[doc["user_id"]] = doc
        return doc

    def update_user(self, doc: Dict) -> Dict:
        doc["id"] = doc.get("id") or doc.get("user_id")
        self.users[doc["user_id"]] = doc
        return doc


def get_repository() -> UserRepository:
    """Get user repository instance (Cosmos or in-memory fallback)."""
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            logger.info("Using Cosmos DB for user storage.")
            return CosmosUserRepository(settings)
        except Exception as exc:  # pragma: no cover - environment specific
            logger.warning("Falling back to in-memory user store: %s", exc)
    logger.info("Using in-memory user storage.")
    return InMemoryUserRepository()

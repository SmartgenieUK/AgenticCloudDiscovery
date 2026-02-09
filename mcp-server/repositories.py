"""Data access layer for MCP Server - reuses orchestrator patterns."""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from azure.cosmos import CosmosClient, PartitionKey
from config import settings
from models import ConnectionDocument, ToolSchema, PolicyDocument

logger = logging.getLogger(__name__)


# ==================== Connection Repository ====================
class ConnectionRepository(ABC):
    """Abstract repository for connection data access."""

    @abstractmethod
    def get_by_id(self, connection_id: str) -> Optional[Dict]:
        pass


class CosmosConnectionRepository(ConnectionRepository):
    """Cosmos DB implementation for connections."""

    def __init__(self, settings):
        self.client = CosmosClient(settings.cosmos_endpoint, settings.cosmos_key)
        self.database = self.client.get_database_client(settings.cosmos_database)
        self.container = self.database.get_container_client(settings.cosmos_container_connections)
        logger.info("CosmosConnectionRepository initialized")

    def get_by_id(self, connection_id: str) -> Optional[Dict]:
        """Get connection by ID."""
        try:
            # Direct read with partition key
            item = self.container.read_item(
                item=connection_id,
                partition_key=connection_id
            )
            return item
        except Exception as e:
            # Fallback to query if direct read fails
            logger.warning(f"Direct read failed for connection {connection_id}, trying query: {e}")
            try:
                query = "SELECT * FROM c WHERE c.connection_id = @connection_id"
                items = list(self.container.query_items(
                    query=query,
                    parameters=[{"name": "@connection_id", "value": connection_id}],
                    enable_cross_partition_query=True
                ))
                return items[0] if items else None
            except Exception as ex:
                logger.error(f"Query also failed for connection {connection_id}: {ex}")
                return None


class InMemoryConnectionRepository(ConnectionRepository):
    """In-memory implementation for testing."""

    def __init__(self):
        self.connections: Dict[str, Dict] = {}
        logger.info("InMemoryConnectionRepository initialized")

    def get_by_id(self, connection_id: str) -> Optional[Dict]:
        return self.connections.get(connection_id)


# ==================== Tool Repository ====================
class ToolRepository(ABC):
    """Abstract repository for tool data access."""

    @abstractmethod
    def get_by_id(self, tool_id: str) -> Optional[Dict]:
        pass

    @abstractmethod
    def list_approved(self) -> List[Dict]:
        pass


class CosmosToolRepository(ToolRepository):
    """Cosmos DB implementation for tools."""

    def __init__(self, settings):
        self.client = CosmosClient(settings.cosmos_endpoint, settings.cosmos_key)
        self.database = self.client.get_database_client(settings.cosmos_database)
        self.container = self.database.get_container_client(settings.cosmos_container_tools)
        logger.info("CosmosToolRepository initialized")

    def get_by_id(self, tool_id: str) -> Optional[Dict]:
        """Get tool by ID."""
        try:
            item = self.container.read_item(
                item=tool_id,
                partition_key=tool_id
            )
            return item
        except Exception as e:
            logger.warning(f"Tool {tool_id} not found: {e}")
            return None

    def list_approved(self) -> List[Dict]:
        """List all approved tools."""
        try:
            query = "SELECT * FROM c WHERE c.status = 'approved'"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            return items
        except Exception as e:
            logger.error(f"Failed to list approved tools: {e}")
            return []


class InMemoryToolRepository(ToolRepository):
    """In-memory implementation for testing."""

    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        logger.info("InMemoryToolRepository initialized")

    def get_by_id(self, tool_id: str) -> Optional[Dict]:
        return self.tools.get(tool_id)

    def list_approved(self) -> List[Dict]:
        return [tool for tool in self.tools.values() if tool.get("status") == "approved"]


# ==================== Policy Repository ====================
class PolicyRepository(ABC):
    """Abstract repository for policy data access."""

    @abstractmethod
    def get_by_id(self, policy_id: str) -> Optional[Dict]:
        pass

    @abstractmethod
    def get_default(self) -> Dict:
        pass


class CosmosPolicyRepository(PolicyRepository):
    """Cosmos DB implementation for policies."""

    def __init__(self, settings):
        self.client = CosmosClient(settings.cosmos_endpoint, settings.cosmos_key)
        self.database = self.client.get_database_client(settings.cosmos_database)
        self.container = self.database.get_container_client(settings.cosmos_container_policies)
        self.settings = settings
        logger.info("CosmosPolicyRepository initialized")

    def get_by_id(self, policy_id: str) -> Optional[Dict]:
        """Get policy by ID."""
        try:
            item = self.container.read_item(
                item=policy_id,
                partition_key=policy_id
            )
            return item
        except Exception as e:
            logger.warning(f"Policy {policy_id} not found: {e}")
            return None

    def get_default(self) -> Dict:
        """Get default policy or return hardcoded defaults."""
        default_policy = self.get_by_id("default")
        if default_policy:
            return default_policy

        # Return hardcoded defaults if no policy in Cosmos
        logger.warning("No default policy found in Cosmos, using hardcoded defaults")
        return {
            "policy_id": "default",
            "allowed_domains": ["management.azure.com"],
            "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "max_payload_bytes": self.settings.default_max_payload_bytes,
            "max_retries": self.settings.default_max_retries,
            "approval_required": self.settings.default_approval_required,
            "max_execution_timeout_ms": 30000
        }


class InMemoryPolicyRepository(PolicyRepository):
    """In-memory implementation for testing."""

    def __init__(self, settings):
        self.policies: Dict[str, Dict] = {}
        self.settings = settings
        logger.info("InMemoryPolicyRepository initialized")

    def get_by_id(self, policy_id: str) -> Optional[Dict]:
        return self.policies.get(policy_id)

    def get_default(self) -> Dict:
        """Return default policy."""
        if "default" in self.policies:
            return self.policies["default"]

        return {
            "policy_id": "default",
            "allowed_domains": ["management.azure.com"],
            "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "max_payload_bytes": self.settings.default_max_payload_bytes,
            "max_retries": self.settings.default_max_retries,
            "approval_required": self.settings.default_approval_required,
            "max_execution_timeout_ms": 30000
        }


# ==================== Repository Factory ====================
def get_connection_repository() -> ConnectionRepository:
    """Factory function for connection repository."""
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            return CosmosConnectionRepository(settings)
        except Exception as e:
            logger.warning(f"Failed to create Cosmos connection repo, falling back to in-memory: {e}")
            return InMemoryConnectionRepository()
    return InMemoryConnectionRepository()


def get_tool_repository() -> ToolRepository:
    """Factory function for tool repository."""
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            return CosmosToolRepository(settings)
        except Exception as e:
            logger.warning(f"Failed to create Cosmos tool repo, falling back to in-memory: {e}")
            return InMemoryToolRepository()
    return InMemoryToolRepository()


def get_policy_repository() -> PolicyRepository:
    """Factory function for policy repository."""
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            return CosmosPolicyRepository(settings)
        except Exception as e:
            logger.warning(f"Failed to create Cosmos policy repo, falling back to in-memory: {e}")
            return InMemoryPolicyRepository(settings)
    return InMemoryPolicyRepository(settings)


# Module-level singletons
connection_repo: ConnectionRepository = get_connection_repository()
tool_repo: ToolRepository = get_tool_repository()
policy_repo: PolicyRepository = get_policy_repository()

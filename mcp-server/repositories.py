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


# Default tool definitions for ARM API discovery
DEFAULT_TOOLS = [
    # --- Core inventory ---
    {
        "tool_id": "inventory_discovery",
        "name": "Inventory Discovery",
        "description": "Read-only inventory of Azure resources for a given subscription.",
        "category": "inventory",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/resources",
        "api_version": "2021-04-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    # --- Service category agents ---
    {
        "tool_id": "compute_discovery",
        "name": "Compute Discovery",
        "description": "List VM instances and their configurations.",
        "category": "compute",
        "provider_namespace": "Microsoft.Compute",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Compute/virtualMachines",
        "api_version": "2024-03-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "storage_discovery",
        "name": "Storage Discovery",
        "description": "List storage accounts and their configurations.",
        "category": "storage",
        "provider_namespace": "Microsoft.Storage",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Storage/storageAccounts",
        "api_version": "2023-05-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "database_discovery",
        "name": "Database Discovery",
        "description": "List SQL servers and database configurations.",
        "category": "databases",
        "provider_namespace": "Microsoft.Sql",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Sql/servers",
        "api_version": "2023-05-01-preview",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "networking_discovery",
        "name": "Networking Discovery",
        "description": "List virtual networks and network configurations.",
        "category": "networking",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/virtualNetworks",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "appservice_discovery",
        "name": "App Services Discovery",
        "description": "List web apps and function apps.",
        "category": "app_services",
        "provider_namespace": "Microsoft.Web",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Web/sites",
        "api_version": "2023-12-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    # --- Layer 2: Topology tools ---
    {
        "tool_id": "nic_discovery",
        "name": "Network Interface Discovery",
        "description": "List network interfaces and their IP configurations.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/networkInterfaces",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "nsg_discovery",
        "name": "NSG Discovery",
        "description": "List network security groups and their rules.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/networkSecurityGroups",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "public_ip_discovery",
        "name": "Public IP Discovery",
        "description": "List public IP addresses.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/publicIPAddresses",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "vnet_peering_discovery",
        "name": "VNet Peering Discovery",
        "description": "List virtual network peerings across all VNets.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/virtualNetworks",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "route_table_discovery",
        "name": "Route Table Discovery",
        "description": "List route tables and their routes.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/routeTables",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "private_endpoint_discovery",
        "name": "Private Endpoint Discovery",
        "description": "List private endpoints.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/privateEndpoints",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "load_balancer_discovery",
        "name": "Load Balancer Discovery",
        "description": "List load balancers and their configurations.",
        "category": "topology",
        "provider_namespace": "Microsoft.Network",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Network/loadBalancers",
        "api_version": "2024-01-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    # --- Layer 3: Identity & Access tools ---
    {
        "tool_id": "role_assignment_discovery",
        "name": "Role Assignment Discovery",
        "description": "List RBAC role assignments at subscription scope.",
        "category": "identity_access",
        "provider_namespace": "Microsoft.Authorization",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleAssignments",
        "api_version": "2022-04-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "role_definition_discovery",
        "name": "Role Definition Discovery",
        "description": "List RBAC role definitions at subscription scope.",
        "category": "identity_access",
        "provider_namespace": "Microsoft.Authorization",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Authorization/roleDefinitions",
        "api_version": "2022-04-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "policy_assignment_discovery",
        "name": "Policy Assignment Discovery",
        "description": "List Azure Policy assignments at subscription scope.",
        "category": "identity_access",
        "provider_namespace": "Microsoft.Authorization",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Authorization/policyAssignments",
        "api_version": "2023-04-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    # --- Resource Graph tools (Layers 1-3) ---
    {
        "tool_id": "rg_inventory_discovery",
        "name": "Resource Graph Inventory",
        "description": "Full resource inventory via Azure Resource Graph KQL.",
        "category": "resource_graph",
        "args_schema": {
            "subscription_ids": {"type": "array", "required": True},
        },
        "endpoint": "/providers/Microsoft.ResourceGraph/resources",
        "api_version": "2022-10-01",
        "allowed_methods": ["POST"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
        "kql_template": "resources | project id, name, type, tenantId, kind, location, resourceGroup, subscriptionId, managedBy, sku, plan, properties, identity, zones, extendedLocation, tags | order by id asc",
    },
    {
        "tool_id": "rg_topology_discovery",
        "name": "Resource Graph Topology",
        "description": "Network topology resources via Azure Resource Graph KQL.",
        "category": "resource_graph",
        "args_schema": {
            "subscription_ids": {"type": "array", "required": True},
        },
        "endpoint": "/providers/Microsoft.ResourceGraph/resources",
        "api_version": "2022-10-01",
        "allowed_methods": ["POST"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
        "kql_template": "resources | where type in~ ('microsoft.network/networkinterfaces', 'microsoft.network/networksecuritygroups', 'microsoft.network/publicipaddresses', 'microsoft.network/virtualnetworks', 'microsoft.network/routetables', 'microsoft.network/privateendpoints', 'microsoft.network/loadbalancers') | project id, name, type, location, resourceGroup, subscriptionId, properties, tags | order by id asc",
    },
    {
        "tool_id": "rg_identity_discovery",
        "name": "Resource Graph Identity",
        "description": "Role assignments and definitions via Azure Resource Graph KQL.",
        "category": "resource_graph",
        "args_schema": {
            "subscription_ids": {"type": "array", "required": True},
        },
        "endpoint": "/providers/Microsoft.ResourceGraph/resources",
        "api_version": "2022-10-01",
        "allowed_methods": ["POST"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
        "kql_template": "authorizationresources | where type in~ ('microsoft.authorization/roleassignments', 'microsoft.authorization/roledefinitions') | project id, name, type, properties, tenantId, subscriptionId | order by id asc",
    },
    {
        "tool_id": "rg_policy_discovery",
        "name": "Resource Graph Policy",
        "description": "Policy assignments via Azure Resource Graph KQL.",
        "category": "resource_graph",
        "args_schema": {
            "subscription_ids": {"type": "array", "required": True},
        },
        "endpoint": "/providers/Microsoft.ResourceGraph/resources",
        "api_version": "2022-10-01",
        "allowed_methods": ["POST"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
        "kql_template": "policyresources | where type =~ 'microsoft.authorization/policyassignments' | project id, name, type, properties, location, subscriptionId | order by id asc",
    },
    # --- Add-on scans (not part of default agent flow) ---
    {
        "tool_id": "cost_discovery",
        "name": "Cost Discovery",
        "description": "Retrieve Azure cost/usage data for an authorized scope.",
        "category": "addon",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query",
        "api_version": "2023-03-01",
        "allowed_methods": ["POST"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
    {
        "tool_id": "security_discovery",
        "name": "Security Discovery",
        "description": "Fetch security posture assessments for an authorized scope.",
        "category": "addon",
        "args_schema": {"subscription_id": {"type": "string", "required": True}},
        "endpoint": "/subscriptions/{subscription_id}/providers/Microsoft.Security/assessments",
        "api_version": "2021-06-01",
        "allowed_methods": ["GET"],
        "allowed_domains": ["management.azure.com"],
        "status": "approved",
        "provenance": "built-in",
    },
]


def seed_default_tools(repo: ToolRepository) -> None:
    """Seed the tool repository with default ARM discovery tools."""
    if isinstance(repo, InMemoryToolRepository):
        for tool in DEFAULT_TOOLS:
            repo.tools[tool["tool_id"]] = tool
        logger.info(f"Seeded {len(DEFAULT_TOOLS)} default tools into in-memory repo")


# Module-level singletons
connection_repo: ConnectionRepository = get_connection_repository()
tool_repo: ToolRepository = get_tool_repository()
policy_repo: PolicyRepository = get_policy_repository()

# Seed default tools for in-memory dev mode
seed_default_tools(tool_repo)

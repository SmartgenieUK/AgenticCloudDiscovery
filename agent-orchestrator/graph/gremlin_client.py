"""Cosmos DB Gremlin API client for graph operations."""
import logging
from typing import Dict, List, Optional

from gremlin_python.driver import client, serializer
from gremlin_python.driver.protocol import GremlinServerError

from config import settings

logger = logging.getLogger("agent-orchestrator.graph.gremlin")


class GremlinGraphClient:
    """Client for Cosmos DB Gremlin API graph operations."""

    def __init__(
        self,
        endpoint: str,
        key: str,
        database: str = "graph-analytics",
        graph: str = "resources"
    ):
        """
        Initialize Gremlin client for Cosmos DB.

        Args:
            endpoint: Cosmos DB endpoint (e.g., wss://xxx.gremlin.cosmos.azure.com:443/)
            key: Cosmos DB primary key
            database: Gremlin database name
            graph: Graph/collection name
        """
        # Cosmos DB Gremlin endpoint format
        if not endpoint.startswith("wss://"):
            # Convert https:// to wss:// and add Gremlin port
            endpoint = endpoint.replace("https://", "wss://").replace(":443/", "")
            endpoint = f"{endpoint}.gremlin.cosmos.azure.com:443/"

        self.endpoint = endpoint
        self.database = database
        self.graph = graph

        # Create Gremlin client
        self.client = client.Client(
            url=self.endpoint,
            traversal_source='g',
            username=f"/dbs/{database}/colls/{graph}",
            password=key,
            message_serializer=serializer.GraphSONSerializersV2d0()
        )

        logger.info(f"Initialized Gremlin client: {endpoint} -> {database}/{graph}")

    def execute(self, query: str, bindings: Optional[Dict] = None) -> List:
        """
        Execute a Gremlin query.

        Args:
            query: Gremlin query string
            bindings: Query parameter bindings

        Returns:
            List of query results
        """
        try:
            callback = self.client.submitAsync(query, bindings or {})
            results = callback.result()
            return list(results)
        except GremlinServerError as e:
            logger.error(f"Gremlin query failed: {query} - Error: {e}")
            raise

    def add_vertex(self, label: str, properties: Dict) -> Dict:
        """
        Add a vertex (node) to the graph.

        Args:
            label: Vertex label (e.g., 'resource', 'subscription')
            properties: Vertex properties

        Returns:
            Created vertex
        """
        # Build property string
        prop_parts = [f".property('{k}', '{v}')" for k, v in properties.items()]
        prop_string = "".join(prop_parts)

        query = f"g.addV('{label}'){prop_string}"
        result = self.execute(query)
        return result[0] if result else {}

    def add_edge(self, from_id: str, to_id: str, label: str, properties: Optional[Dict] = None) -> Dict:
        """
        Add an edge (relationship) between two vertices.

        Args:
            from_id: Source vertex ID
            to_id: Target vertex ID
            label: Edge label (e.g., 'depends_on', 'contains')
            properties: Optional edge properties

        Returns:
            Created edge
        """
        prop_parts = []
        if properties:
            prop_parts = [f".property('{k}', '{v}')" for k, v in properties.items()]
        prop_string = "".join(prop_parts)

        query = f"""
            g.V('{from_id}')
             .addE('{label}')
             .to(g.V('{to_id}'))
             {prop_string}
        """
        result = self.execute(query)
        return result[0] if result else {}

    def find_vertex(self, vertex_id: str) -> Optional[Dict]:
        """Find a vertex by ID."""
        query = f"g.V('{vertex_id}')"
        result = self.execute(query)
        return result[0] if result else None

    def find_dependencies(self, vertex_id: str, max_depth: int = 5) -> List[Dict]:
        """
        Find all dependencies of a resource (outbound edges).

        Args:
            vertex_id: Resource vertex ID
            max_depth: Maximum traversal depth

        Returns:
            List of dependent resources
        """
        query = f"""
            g.V('{vertex_id}')
             .repeat(out('depends_on')).times({max_depth})
             .emit()
             .dedup()
        """
        return self.execute(query)

    def find_dependents(self, vertex_id: str) -> List[Dict]:
        """
        Find all resources that depend on this resource (inbound edges).

        Args:
            vertex_id: Resource vertex ID

        Returns:
            List of dependent resources
        """
        query = f"""
            g.V('{vertex_id}')
             .in('depends_on')
             .dedup()
        """
        return self.execute(query)

    def find_blast_radius(self, vertex_id: str) -> Dict:
        """
        Find blast radius: all upstream and downstream dependencies.

        Args:
            vertex_id: Resource vertex ID

        Returns:
            Dict with upstream, downstream, and total counts
        """
        upstream = self.find_dependents(vertex_id)
        downstream = self.find_dependencies(vertex_id)

        return {
            "resource_id": vertex_id,
            "upstream_count": len(upstream),
            "downstream_count": len(downstream),
            "total_blast_radius": len(upstream) + len(downstream),
            "upstream": upstream,
            "downstream": downstream
        }

    def find_orphaned_resources(self, subscription_id: str) -> List[Dict]:
        """
        Find resources with no dependencies (potential waste).

        Args:
            subscription_id: Subscription to search

        Returns:
            List of orphaned resources
        """
        query = f"""
            g.V()
             .has('subscription_id', '{subscription_id}')
             .not(out('depends_on'))
             .not(in('depends_on'))
        """
        return self.execute(query)

    def get_graph_statistics(self, subscription_id: str) -> Dict:
        """
        Get graph statistics for a subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            Statistics dict
        """
        vertex_count = self.execute(f"g.V().has('subscription_id', '{subscription_id}').count()")
        edge_count = self.execute(f"g.E().count()")

        return {
            "subscription_id": subscription_id,
            "vertex_count": vertex_count[0] if vertex_count else 0,
            "edge_count": edge_count[0] if edge_count else 0
        }

    def clear_graph(self, subscription_id: Optional[str] = None):
        """
        Clear graph data (use with caution!).

        Args:
            subscription_id: If provided, only clear this subscription's data
        """
        if subscription_id:
            query = f"g.V().has('subscription_id', '{subscription_id}').drop()"
        else:
            query = "g.V().drop()"

        self.execute(query)
        logger.warning(f"Cleared graph data: {subscription_id or 'ALL'}")


def get_graph_client() -> Optional[GremlinGraphClient]:
    """
    Get Gremlin graph client instance.

    Returns:
        GremlinGraphClient if Gremlin endpoint configured, None otherwise
    """
    if not settings.cosmos_endpoint or not settings.cosmos_key:
        logger.warning("Cosmos DB not configured, graph operations disabled")
        return None

    try:
        return GremlinGraphClient(
            endpoint=settings.cosmos_endpoint,
            key=settings.cosmos_key,
            database="graph-analytics",
            graph="resources"
        )
    except Exception as e:
        logger.error(f"Failed to initialize Gremlin client: {e}")
        return None

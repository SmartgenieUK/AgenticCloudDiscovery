"""Service to sync discovery results to Cosmos DB Gremlin graph."""
import logging
from typing import Dict, List

from .gremlin_client import GremlinGraphClient

logger = logging.getLogger("agent-orchestrator.graph.sync")


class GraphSyncService:
    """Syncs discovery results from Cosmos SQL to Gremlin graph."""

    def __init__(self, graph_client: GremlinGraphClient):
        self.graph = graph_client

    def sync_inventory_discovery(self, discovery: Dict) -> Dict:
        """
        Sync inventory discovery results to graph.

        Args:
            discovery: Discovery document from Cosmos SQL API

        Returns:
            Sync statistics
        """
        discovery_id = discovery["discovery_id"]
        subscription_id = discovery.get("subscription_id")
        tenant_id = discovery.get("tenant_id")

        logger.info(f"Syncing discovery {discovery_id} to graph...")

        # Extract resources from discovery results
        resources = discovery.get("results", {}).get("formatted", {}).get("resources", [])
        if not resources:
            logger.warning(f"No resources found in discovery {discovery_id}")
            return {"vertices_created": 0, "edges_created": 0}

        vertices_created = 0
        edges_created = 0

        # Create subscription vertex if not exists
        sub_vertex = self.graph.find_vertex(subscription_id)
        if not sub_vertex:
            self.graph.add_vertex("subscription", {
                "id": subscription_id,
                "tenant_id": tenant_id,
                "name": f"Subscription {subscription_id[:8]}...",
                "discovery_id": discovery_id
            })
            vertices_created += 1

        # Create resource vertices
        for resource in resources:
            resource_id = resource.get("id")
            if not resource_id:
                continue

            # Check if vertex exists
            existing = self.graph.find_vertex(resource_id)
            if not existing:
                self.graph.add_vertex("resource", {
                    "id": resource_id,
                    "name": resource.get("name", ""),
                    "type": resource.get("type", ""),
                    "resource_group": resource.get("resource_group", ""),
                    "location": resource.get("location", ""),
                    "subscription_id": subscription_id,
                    "discovery_id": discovery_id
                })
                vertices_created += 1

            # Create containment edge (subscription → resource)
            try:
                self.graph.add_edge(
                    from_id=subscription_id,
                    to_id=resource_id,
                    label="contains",
                    properties={"discovery_id": discovery_id}
                )
                edges_created += 1
            except Exception as e:
                logger.warning(f"Failed to create containment edge: {e}")

            # Create dependency edges
            for dep in resource.get("dependencies", []):
                dep_id = dep.get("id")
                if not dep_id:
                    continue

                try:
                    self.graph.add_edge(
                        from_id=resource_id,
                        to_id=dep_id,
                        label="depends_on",
                        properties={
                            "discovery_id": discovery_id,
                            "dependency_type": dep.get("type", "unknown")
                        }
                    )
                    edges_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create dependency edge {resource_id} -> {dep_id}: {e}")

        stats = {
            "discovery_id": discovery_id,
            "vertices_created": vertices_created,
            "edges_created": edges_created
        }

        logger.info(f"Graph sync complete: {stats}")
        return stats

    def sync_cost_flow(self, discovery: Dict) -> Dict:
        """
        Sync cost discovery as a flow graph (budget → services → resources).

        Args:
            discovery: Cost discovery document

        Returns:
            Sync statistics
        """
        discovery_id = discovery["discovery_id"]
        subscription_id = discovery.get("subscription_id")

        cost_data = discovery.get("results", {}).get("formatted", {})
        total_cost = cost_data.get("total_cost", 0)

        vertices_created = 0
        edges_created = 0

        # Create budget node
        budget_id = f"budget-{subscription_id}"
        self.graph.add_vertex("budget", {
            "id": budget_id,
            "subscription_id": subscription_id,
            "total_cost": str(total_cost),
            "discovery_id": discovery_id
        })
        vertices_created += 1

        # Create service cost nodes and edges
        for service in cost_data.get("by_service", []):
            service_id = f"service-{service['service'].replace(' ', '-')}"

            self.graph.add_vertex("service", {
                "id": service_id,
                "name": service["service"],
                "cost": str(service["cost"]),
                "discovery_id": discovery_id
            })
            vertices_created += 1

            # Budget → Service edge with cost
            self.graph.add_edge(
                from_id=budget_id,
                to_id=service_id,
                label="costs",
                properties={
                    "amount": str(service["cost"]),
                    "percentage": str(service.get("percentage", 0)),
                    "discovery_id": discovery_id
                }
            )
            edges_created += 1

        return {
            "discovery_id": discovery_id,
            "vertices_created": vertices_created,
            "edges_created": edges_created
        }

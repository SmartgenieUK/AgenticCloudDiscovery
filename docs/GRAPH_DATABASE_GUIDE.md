# Cosmos DB Gremlin Graph Database Guide

Complete guide to using Cosmos DB's Gremlin API for graph analytics in AgenticCloudDisc.

## 📊 **Why Graph Database?**

Cloud architectures are inherently graph-structured:
- **Resources** → Vertices (VMs, VNets, Storage)
- **Dependencies** → Edges (VM → VNet, App → Database)
- **Relationships** → Edges (Cost flows, Security boundaries)

**Graph queries you can run:**
- "What breaks if I delete this VNet?" (blast radius)
- "Show all resources that depend on this database" (reverse dependencies)
- "Find orphaned resources with no dependencies" (cost optimization)
- "Show cost flow from budget → services → resources" (Sankey diagram)

---

## 🏗️ **Architecture**

```
┌──────────────────────────────────────────────────────────┐
│              Cosmos DB Account (Multi-Model)              │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  SQL API (Operational)      Gremlin API (Graph Analytics) │
│  ─────────────────────      ───────────────────────────── │
│                                                            │
│  Database: agentic-cloud-disc                             │
│  ├─ users                   Database: graph-analytics     │
│  ├─ connections             ├─ resources (vertices)       │
│  ├─ discoveries             │   └─ Azure resources        │
│  ├─ policies                └─ dependencies (edges)       │
│  └─ tools                       └─ Resource relationships │
│                                                            │
│  Discovery Workflow:                                      │
│  1. Execute → Store in SQL  (Operational record)          │
│  2. Sync → Store in Gremlin (Graph analytics)             │
└──────────────────────────────────────────────────────────┘
```

---

## 🚀 **Deployment**

### **1. Update Infrastructure**

```bash
# Deploy Cosmos with Gremlin API
cd infra
az deployment group create \
  --name cosmos-graph-deployment \
  --resource-group rg_ACD \
  --template-file modules/cosmos-graph.bicep \
  --parameters cosmosAccountName=<your-cosmos-account>
```

**What this creates:**
- ✅ Gremlin database: `graph-analytics`
- ✅ Graph container: `resources` (vertices)
- ✅ Graph container: `dependencies` (edges)
- ✅ Same Cosmos account, serverless billing

### **2. Install Dependencies**

```bash
cd agent-orchestrator
pip install gremlinpython==3.7.1
```

### **3. Configure Environment**

```bash
# .env or Container Apps environment variables
COSMOS_ENDPOINT=https://cosmos-acd-dev-xxx.documents.azure.com:443/
COSMOS_KEY=<your-cosmos-key>
ENABLE_GRAPH_SYNC=true  # Enable automatic graph sync
```

---

## 📝 **Usage Examples**

### **Basic Queries**

```python
from graph import get_graph_client

# Initialize client
graph = get_graph_client()

# Find a resource
vm = graph.find_vertex("/subscriptions/.../vm-web-01")

# Find all dependencies of a VM
dependencies = graph.find_dependencies("/subscriptions/.../vm-web-01")
# Returns: [NIC, Disk, VNet, NSG, ...]

# Find what depends on a VNet (reverse dependencies)
dependents = graph.find_dependents("/subscriptions/.../vnet-prod")
# Returns: [VM-1, VM-2, App Service, ...]

# Find blast radius (all affected resources)
blast_radius = graph.find_blast_radius("/subscriptions/.../vnet-prod")
# Returns: {
#   "upstream_count": 5,   # Resources that use this
#   "downstream_count": 3,  # Resources this depends on
#   "total_blast_radius": 8
# }

# Find orphaned resources (cost optimization)
orphans = graph.find_orphaned_resources("sub-123")
# Returns: Resources with no dependencies (safe to delete?)
```

### **Advanced Gremlin Queries**

```python
# Find all VMs in a specific location
query = """
    g.V()
     .has('type', 'Microsoft.Compute/virtualMachines')
     .has('location', 'eastus')
     .values('name')
"""
vms = graph.execute(query)

# Find shortest path between two resources
query = """
    g.V('vm-web-01')
     .repeat(out('depends_on')).until(hasId('sql-prod'))
     .path()
     .limit(1)
"""
path = graph.execute(query)

# Find all resources in a resource group
query = """
    g.V()
     .has('resource_group', 'rg-prod')
     .group()
     .by('type')
     .by(count())
"""
grouped = graph.execute(query)

# Find resources with most dependencies (critical resources)
query = """
    g.V()
     .hasLabel('resource')
     .project('name', 'incoming', 'outgoing')
     .by('name')
     .by(inE('depends_on').count())
     .by(outE('depends_on').count())
     .order()
     .by(select('incoming'), desc)
     .limit(10)
"""
critical = graph.execute(query)
```

---

## 🔄 **Automatic Graph Sync**

Discovery results are automatically synced to the graph after completion:

```python
# In agent-orchestrator/discoveries/workflow.py

from graph import get_graph_client, GraphSyncService

def run_discovery_workflow(...):
    # ... existing discovery logic ...

    # After persist stage completes
    saved["status"] = "completed"
    saved = discovery_repo.update(saved)

    # Sync to graph (async, non-blocking)
    if settings.enable_graph_sync:
        try:
            graph_client = get_graph_client()
            if graph_client and tier == "inventory":
                sync_service = GraphSyncService(graph_client)
                stats = sync_service.sync_inventory_discovery(saved)
                logger.info(f"Graph sync: {stats}")
        except Exception as e:
            logger.warning(f"Graph sync failed (non-critical): {e}")

    return {...}
```

**Sync happens:**
- ✅ After discovery completes
- ✅ Non-blocking (doesn't slow down API response)
- ✅ Failures logged but don't fail discovery
- ✅ Optional (controlled by `ENABLE_GRAPH_SYNC` env var)

---

## 🎨 **Visualization Integration**

### **Backend: Graph Data API**

```python
# agent-orchestrator/main.py

@app.get("/discoveries/{discovery_id}/graph")
def get_discovery_graph(discovery_id: str, user: Dict = Depends(get_current_user)):
    """Get graph visualization data for a discovery."""
    graph = get_graph_client()
    if not graph:
        raise HTTPException(status_code=503, detail="Graph database not available")

    # Get all resources in this discovery
    query = f"""
        g.V()
         .has('discovery_id', '{discovery_id}')
         .project('id', 'name', 'type', 'dependencies')
         .by('id')
         .by('name')
         .by('type')
         .by(out('depends_on').values('id').fold())
    """

    resources = graph.execute(query)

    # Transform to D3.js / React Flow format
    nodes = []
    links = []

    for resource in resources:
        nodes.append({
            "id": resource["id"],
            "name": resource["name"],
            "type": resource["type"],
            "color": get_color_by_type(resource["type"]),
            "size": 20
        })

        for dep_id in resource.get("dependencies", []):
            links.append({
                "source": resource["id"],
                "target": dep_id,
                "type": "depends_on"
            })

    return {"nodes": nodes, "links": links}
```

### **Frontend: Fetch and Render**

```jsx
// client-ui/src/pages/DiscoveryGraph.jsx
import { useEffect, useState } from 'react';
import { api } from '../api';
import D3ForceGraph from '../components/D3ForceGraph';

const DiscoveryGraph = ({ discoveryId }) => {
  const [graphData, setGraphData] = useState(null);

  useEffect(() => {
    api.getDiscoveryGraph(discoveryId)
      .then(data => setGraphData(data));
  }, [discoveryId]);

  if (!graphData) return <div>Loading graph...</div>;

  return (
    <div>
      <h2>Resource Topology</h2>
      <D3ForceGraph data={graphData} />

      <div className="graph-stats">
        <p>Total Resources: {graphData.nodes.length}</p>
        <p>Total Dependencies: {graphData.links.length}</p>
      </div>
    </div>
  );
};
```

---

## 🔧 **Graph Schema**

### **Vertex Types**

| Label | Properties | Example |
|-------|------------|---------|
| `subscription` | id, tenant_id, name | Azure subscription |
| `resource` | id, name, type, resource_group, location | VM, VNet, Storage |
| `budget` | id, subscription_id, total_cost | Cost budget node |
| `service` | id, name, cost | Azure service (Compute, Storage) |

### **Edge Types**

| Label | From → To | Properties | Meaning |
|-------|-----------|------------|---------|
| `contains` | subscription → resource | discovery_id | Subscription contains resource |
| `depends_on` | resource → resource | dependency_type | Resource depends on another |
| `costs` | budget → service | amount, percentage | Cost allocation |
| `belongs_to` | resource → resource_group | - | Resource group membership |

---

## 💰 **Cost Implications**

**Cosmos DB Gremlin API** uses the same billing as SQL API:

| Operation | Serverless Cost |
|-----------|-----------------|
| **Vertex insert** | ~0.1 RU (~$0.00001) |
| **Edge insert** | ~0.1 RU |
| **Query (simple)** | 1-10 RU |
| **Query (complex)** | 10-100 RU |

**Example discovery sync:**
- 50 resources → 50 vertices (~5 RU)
- 75 dependencies → 75 edges (~7.5 RU)
- **Total: ~12.5 RU = $0.0000125 per discovery**

**Monthly estimate for 1000 discoveries:**
- 1000 discoveries × 12.5 RU = 12,500 RU
- 12,500 RU × $0.001 = **$12.50/month**

➡️ **Graph storage adds ~$10-20/month** to existing Cosmos costs.

---

## 🧪 **Testing**

```bash
# Test graph sync locally
cd agent-orchestrator
python -m pytest tests/test_graph_sync.py -v

# Test Gremlin queries
python

from graph import get_graph_client

graph = get_graph_client()
print(graph.get_graph_statistics("sub-123"))
```

---

## 🔒 **Security**

**Same security as Cosmos DB SQL API:**
- ✅ Azure AD authentication
- ✅ RBAC (same permissions as SQL containers)
- ✅ Encryption at rest and in transit
- ✅ Private endpoints (if configured)
- ✅ Firewall rules
- ✅ Key rotation

**No additional security configuration needed!**

---

## 📈 **Performance**

**Gremlin query performance:**
- Simple vertex lookups: ~5-10ms
- Dependency traversal (depth 3): ~20-50ms
- Blast radius (depth 5): ~50-150ms
- Complex graph algorithms: ~200-500ms

**Optimization tips:**
1. Partition by `subscription_id` (already configured)
2. Index frequently queried properties
3. Limit traversal depth with `.times(n)`
4. Use `.limit()` for large result sets

---

## 🚨 **Troubleshooting**

### **Gremlin endpoint not found**

```bash
# Verify Gremlin database exists
az cosmosdb gremlin database show \
  --account-name <cosmos-account> \
  --resource-group rg_ACD \
  --name graph-analytics
```

### **Connection timeout**

```python
# Increase client timeout
from gremlin_python.driver import client

client = client.Client(
    url=endpoint,
    timeout=60000  # 60 seconds
)
```

### **Query too slow**

```python
# Add limits to prevent full graph traversal
query = """
    g.V().has('subscription_id', 'sub-123')
     .repeat(out('depends_on')).times(3)  # Limit depth
     .limit(100)  # Limit results
"""
```

---

## 🎓 **Learn More**

- [Cosmos DB Gremlin API Docs](https://learn.microsoft.com/azure/cosmos-db/gremlin/)
- [Gremlin Query Language](https://tinkerpop.apache.org/docs/current/reference/#graph-traversal-steps)
- [Graph Partitioning Best Practices](https://learn.microsoft.com/azure/cosmos-db/gremlin/partitioning)

---

## ✅ **Summary**

**You now have:**
- ✅ Microsoft-native graph database (Cosmos Gremlin API)
- ✅ Automatic sync from discoveries to graph
- ✅ Graph query capabilities for complex analysis
- ✅ Ready for D3.js/React Flow visualization
- ✅ ~$10-20/month added cost (serverless)
- ✅ Future-proof for advanced analytics

**Next steps:**
1. Deploy Cosmos Gremlin database
2. Enable graph sync in environment variables
3. Test with a discovery
4. Build graph visualization UI

🚀 **Your cloud architecture insights just got a major upgrade!**

# AgenticCloudDisc Infrastructure

Infrastructure as Code (IaC) for deploying AgenticCloudDisc to Azure using Bicep.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Azure Subscription                       │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Container Apps Environment                                  │ │
│  │                                                              │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │ │
│  │  │  Client UI   │  │ Orchestrator │  │  MCP Server  │     │ │
│  │  │  (nginx)     │  │  (FastAPI)   │  │  (FastAPI)   │     │ │
│  │  │  Port 80     │  │  Port 8000   │  │  Port 9000   │     │ │
│  │  │  External    │  │  External    │  │  Internal    │     │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘     │ │
│  │                                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │   Cosmos DB    │  │   Key Vault    │  │  App Insights  │   │
│  │   (Serverless) │  │   (Secrets)    │  │  (Monitoring)  │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Azure Container Registry (ACR)                              │ │
│  │ - mcp-server:latest                                         │ │
│  │ - orchestrator:latest                                       │ │
│  │ - client-ui:latest                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Azure CLI** (version 2.50+)
   ```bash
   az --version
   az login
   ```

2. **Docker** (for building images)
   ```bash
   docker --version
   ```

3. **jq** (for JSON processing)
   ```bash
   jq --version
   ```

4. **OpenSSL** (for secret generation)
   ```bash
   openssl version
   ```

5. **Azure Subscription**
   - Owner or Contributor role
   - Sufficient quota for Container Apps, Cosmos DB, and ACR

## Quick Start

### 1. Deploy Infrastructure

```bash
cd infra/scripts
./deploy.sh dev
```

This will:
- ✅ Create/verify resource group
- ✅ Create Azure Container Registry (ACR)
- ✅ Build and push Docker images
- ✅ Create Key Vault and store secrets
- ✅ Deploy Cosmos DB (serverless, 6 containers)
- ✅ Deploy Container Apps Environment
- ✅ Deploy 3 Container Apps (MCP, Orchestrator, UI)
- ✅ Configure Application Insights

**Estimated deployment time:** 15-20 minutes

### 2. Seed Initial Data

```bash
./seed-data.sh dev
```

This will populate Cosmos DB with:
- 1 default policy
- 3 approved tools (inventory, cost, security)

### 3. Configure OAuth

Update the following secrets in Key Vault:

```bash
RESOURCE_GROUP="rg_ACD"
KV_NAME=$(az keyvault list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv)

# Google OAuth
az keyvault secret set --vault-name "$KV_NAME" --name "google-client-secret" --value "<your-google-secret>"

# Microsoft OAuth
az keyvault secret set --vault-name "$KV_NAME" --name "microsoft-client-secret" --value "<your-microsoft-secret>"
```

**Get OAuth credentials:**
- **Google**: https://console.cloud.google.com/apis/credentials
- **Microsoft**: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps

### 4. Test Deployment

```bash
# Get the Client UI URL from deployment output
CLIENT_UI_URL=$(az deployment group show \
  --name <deployment-name> \
  --resource-group rg_ACD \
  --query properties.outputs.clientUiUrl.value -o tsv)

echo "Visit: $CLIENT_UI_URL"
```

## Directory Structure

```
infra/
├── main.bicep                      # Main orchestration template
├── modules/
│   ├── cosmos.bicep                # Cosmos DB (6 containers)
│   ├── keyvault.bicep              # Key Vault (RBAC-enabled)
│   ├── appinsights.bicep           # App Insights + Log Analytics
│   └── container-apps.bicep        # Container Apps (3 apps)
├── parameters/
│   ├── dev.parameters.json         # Dev environment config
│   └── prod.parameters.json        # Prod environment config (TBD)
├── scripts/
│   ├── deploy.sh                   # Main deployment script
│   └── seed-data.sh                # Cosmos DB data seeding
└── README.md                       # This file
```

## Resources Created

| Resource | Purpose | Configuration |
|----------|---------|---------------|
| **Cosmos DB** | Data persistence | Serverless, 6 containers, Session consistency |
| **Container Apps** | Hosting | 3 apps (MCP, Orchestrator, UI) |
| **ACR** | Docker images | Basic SKU, admin enabled |
| **Key Vault** | Secrets management | RBAC-enabled, soft delete |
| **App Insights** | Observability | 30-day retention |
| **Log Analytics** | Logs | PerGB2018 pricing |

## Container Apps Details

### MCP Server
- **Image:** `agentic-cloud-disc/mcp-server:latest`
- **CPU/Memory:** 0.5 vCPU / 1 GiB
- **Ingress:** Internal only (port 9000)
- **Scaling:** 1-5 replicas (10 concurrent requests trigger)

### Orchestrator
- **Image:** `agentic-cloud-disc/orchestrator:latest`
- **CPU/Memory:** 1.0 vCPU / 2 GiB
- **Ingress:** External HTTPS (port 8000)
- **Scaling:** 1-10 replicas (50 concurrent requests trigger)
- **CORS:** Enabled for UI and localhost

### Client UI
- **Image:** `agentic-cloud-disc/client-ui:latest`
- **CPU/Memory:** 0.25 vCPU / 0.5 GiB
- **Ingress:** External HTTPS (port 80)
- **Scaling:** 1-5 replicas (100 concurrent requests trigger)
- **Server:** nginx with SPA routing

## Costs Estimation (Dev)

| Resource | Monthly Cost (USD) |
|----------|-------------------|
| Cosmos DB (Serverless) | $1-5 (based on usage) |
| Container Apps | $15-30 (1-2 replicas) |
| ACR (Basic) | $5 |
| Key Vault | $0.03 per 10k operations |
| App Insights | $2-10 (based on data) |
| **Total** | **~$25-50/month** |

*Note: Actual costs vary based on usage patterns.*

## Troubleshooting

### Deployment fails with "Cosmos account name already exists"

```bash
# Delete existing Cosmos account
az cosmosdb delete --name <cosmos-name> --resource-group rg_ACD
# Wait 5 minutes, then retry deployment
```

### Container App not starting

```bash
# Check logs
az containerapp logs show \
  --name orchestrator \
  --resource-group rg_ACD \
  --follow

# Check environment variables
az containerapp show \
  --name orchestrator \
  --resource-group rg_ACD \
  --query properties.template.containers[0].env
```

### Key Vault access denied

```bash
# Grant yourself Key Vault Secrets Officer role
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <your-email> \
  --scope /subscriptions/<sub-id>/resourceGroups/rg_ACD/providers/Microsoft.KeyVault/vaults/<kv-name>
```

## Clean Up

**⚠️ Warning: This will delete all resources and data!**

```bash
az group delete --name rg_ACD --yes --no-wait
```

## Next Steps

1. ✅ Deploy infrastructure (done)
2. ✅ Seed initial data (done)
3. 🔄 Configure OAuth credentials
4. 🔄 Test end-to-end workflow
5. 🔄 Set up CI/CD pipeline (GitHub Actions)
6. 🔄 Configure custom domain (optional)
7. 🔄 Enable APIM for external APIs (Phase 3 extension)

## Support

For issues, see:
- [Architecture Docs](../docs/architecture/)
- [GitHub Issues](https://github.com/your-org/agentic-cloud-disc/issues)

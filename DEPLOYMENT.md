# AgenticCloudDisc Deployment Guide

Complete guide for deploying AgenticCloudDisc to Azure Container Apps.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Azure Deployment](#azure-deployment)
4. [Post-Deployment Configuration](#post-deployment-configuration)
5. [Monitoring & Operations](#monitoring--operations)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

```bash
# Azure CLI (2.50+)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
az --version

# Docker (20.10+)
docker --version

# jq (for JSON processing)
sudo apt-get install jq  # Ubuntu/Debian
brew install jq          # macOS

# OpenSSL (for secret generation)
openssl version
```

### Azure Requirements

- **Azure subscription** with Owner or Contributor role
- **Quota availability** for:
  - Container Apps (3 apps)
  - Cosmos DB (1 account)
  - Container Registry (1 registry)
  - Key Vault (1 vault)

### OAuth Setup (Optional but Recommended)

Before deployment, create OAuth applications:

#### Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create new OAuth 2.0 Client ID
3. Set authorized redirect URI:
   - `https://<your-orchestrator-url>/auth/oauth/google/callback`
4. Save **Client ID** and **Client Secret**

#### Microsoft OAuth
1. Go to [Azure Portal - App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps)
2. Register new application
3. Add redirect URI:
   - `https://<your-orchestrator-url>/auth/oauth/microsoft/callback`
4. Create client secret in "Certificates & secrets"
5. Save **Application (client) ID** and **Client Secret**

---

## Local Development

### Option 1: Direct Execution (Recommended for Development)

```bash
# Terminal 1: MCP Server
cd mcp-server
pip install -r requirements.txt
uvicorn main:app --reload --port 9000

# Terminal 2: Orchestrator
cd agent-orchestrator
pip install -r requirements.txt
export MCP_STUB_MODE=true
export MCP_BASE_URL=http://localhost:9000
export SECRET_KEY=dev-secret-key-change-in-production
uvicorn main:app --reload --port 8000

# Terminal 3: Client UI
cd client-ui
npm install
npm run dev  # Runs on http://localhost:5173
```

**Test local setup:**
```bash
# Health checks
curl http://localhost:9000/health    # MCP Server
curl http://localhost:8000/healthz   # Orchestrator
curl http://localhost:5173           # Client UI
```

### Option 2: Docker Compose (Testing Containerized Builds)

```bash
# Build and run all services
docker-compose up --build

# Services will be available at:
# - MCP Server:    http://localhost:9000
# - Orchestrator:  http://localhost:8000
# - Client UI:     http://localhost:3000
```

**Stop services:**
```bash
docker-compose down
```

---

## Azure Deployment

### Step 1: Login to Azure

```bash
az login
az account set --subscription <subscription-id>
az account show
```

### Step 2: Deploy Infrastructure

```bash
cd infra/scripts
./deploy.sh dev
```

**What this does:**
1. ✅ Creates resource group `rg_ACD`
2. ✅ Creates Azure Container Registry
3. ✅ Builds Docker images for all 3 services
4. ✅ Pushes images to ACR
5. ✅ Generates JWT secret
6. ✅ Creates Key Vault with secrets
7. ✅ Deploys Cosmos DB (serverless, 6 containers)
8. ✅ Deploys Container Apps Environment
9. ✅ Deploys 3 Container Apps (MCP, Orchestrator, UI)
10. ✅ Configures Application Insights

**Expected output:**
```
=========================================
🎉 Deployment Successful!
=========================================
Environment: dev
Resource Group: rg_ACD

📍 URLs:
  Client UI:     https://client-ui.xxx.eastus.azurecontainerapps.io
  Orchestrator:  https://orchestrator.xxx.eastus.azurecontainerapps.io

📦 Resources:
  Cosmos DB:     https://cosmos-acd-dev-xxx.documents.azure.com:443/
  Container Registry: acracddev.azurecr.io
=========================================
```

**Deployment time:** ~15-20 minutes

### Step 3: Seed Initial Data

```bash
./seed-data.sh dev
```

**What this does:**
- ✅ Seeds default policy (domain/method allowlists)
- ✅ Seeds 3 approved tools (inventory, cost, security)

---

## Post-Deployment Configuration

### 1. Update OAuth Secrets

Get Key Vault name:
```bash
RESOURCE_GROUP="rg_ACD"
KV_NAME=$(az keyvault list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv)
echo "Key Vault: $KV_NAME"
```

Set OAuth secrets:
```bash
# Google
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "google-client-secret" \
  --value "<your-google-client-secret>"

# Microsoft
az keyvault secret set \
  --vault-name "$KV_NAME" \
  --name "microsoft-client-secret" \
  --value "<your-microsoft-client-secret>"
```

### 2. Update OAuth Client IDs

Update Container App environment variables:
```bash
# Update orchestrator with real OAuth client IDs
az containerapp update \
  --name orchestrator \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars \
    GOOGLE_CLIENT_ID="<your-google-client-id>" \
    MICROSOFT_CLIENT_ID="<your-microsoft-client-id>"
```

### 3. Restart Orchestrator

```bash
az containerapp revision restart \
  --name orchestrator \
  --resource-group "$RESOURCE_GROUP"
```

### 4. Test OAuth Flows

1. Visit Client UI URL
2. Click "Login with Google" or "Login with Microsoft"
3. Verify redirect and authentication works
4. Check that user is created in Cosmos DB `users` container

---

## Monitoring & Operations

### View Application Logs

```bash
# Orchestrator logs
az containerapp logs show \
  --name orchestrator \
  --resource-group rg_ACD \
  --follow

# MCP Server logs
az containerapp logs show \
  --name mcp-server \
  --resource-group rg_ACD \
  --follow

# Client UI logs
az containerapp logs show \
  --name client-ui \
  --resource-group rg_ACD \
  --follow
```

### View Application Insights

```bash
# Get Application Insights URL
az monitor app-insights component show \
  --resource-group rg_ACD \
  --query "[0].{Name:name, AppId:appId}" \
  --output table

# Open in portal
az monitor app-insights component show-web-url \
  --resource-group rg_ACD
```

### Check Container App Status

```bash
# List all apps
az containerapp list \
  --resource-group rg_ACD \
  --output table

# Get specific app details
az containerapp show \
  --name orchestrator \
  --resource-group rg_ACD \
  --query "properties.{ProvisioningState:provisioningState, RunningStatus:runningStatus, FQDN:configuration.ingress.fqdn}"
```

### Query Cosmos DB

```bash
# Get Cosmos account name
COSMOS_ACCOUNT=$(az cosmosdb list --resource-group rg_ACD --query "[0].name" -o tsv)

# List databases
az cosmosdb sql database list \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group rg_ACD

# List containers
az cosmosdb sql container list \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group rg_ACD \
  --database-name agentic-cloud-disc

# Query items (example: list all users)
az cosmosdb sql container query \
  --account-name "$COSMOS_ACCOUNT" \
  --resource-group rg_ACD \
  --database-name agentic-cloud-disc \
  --container-name users \
  --query "SELECT * FROM c"
```

### Scale Container Apps

```bash
# Scale orchestrator to handle more load
az containerapp update \
  --name orchestrator \
  --resource-group rg_ACD \
  --min-replicas 2 \
  --max-replicas 20

# Scale down to save costs
az containerapp update \
  --name orchestrator \
  --resource-group rg_ACD \
  --min-replicas 0 \
  --max-replicas 5
```

---

## Troubleshooting

### Container App Not Starting

**Check revision status:**
```bash
az containerapp revision list \
  --name orchestrator \
  --resource-group rg_ACD \
  --output table
```

**Check logs for errors:**
```bash
az containerapp logs show \
  --name orchestrator \
  --resource-group rg_ACD \
  --tail 100
```

**Common issues:**
- ❌ Missing environment variables → Check `az containerapp show`
- ❌ Image pull failure → Verify ACR credentials
- ❌ Port mismatch → Ensure container exposes correct port
- ❌ Health check failing → Check `/health` endpoint

### OAuth Callback Errors

**Error: "Redirect URI mismatch"**
- Solution: Update OAuth app redirect URIs to match deployed orchestrator FQDN

**Error: "Invalid client secret"**
- Solution: Verify secrets in Key Vault match OAuth app credentials

```bash
# Check current secret value
az keyvault secret show \
  --vault-name "$KV_NAME" \
  --name google-client-secret \
  --query value -o tsv
```

### Cosmos DB Connection Issues

**Error: "Unauthorized" or "Forbidden"**
- Solution: Verify Cosmos key is correct

```bash
# Get primary key
az cosmosdb keys list \
  --name "$COSMOS_ACCOUNT" \
  --resource-group rg_ACD \
  --query primaryMasterKey -o tsv
```

**Error: "Database or container not found"**
- Solution: Run seed script to create containers

```bash
cd infra/scripts
./seed-data.sh dev
```

### High Costs

**Check current spending:**
```bash
az consumption usage list \
  --start-date $(date -d '30 days ago' +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d) \
  --query "[?contains(instanceName, 'acd')].{Name:instanceName, Cost:pretaxCost}" \
  --output table
```

**Cost optimization tips:**
- Scale down min replicas to 0 for non-production
- Use Cosmos DB serverless (already configured)
- Delete unused Container App revisions
- Set budget alerts in Azure portal

### Performance Issues

**Check Application Insights performance:**
```bash
az monitor app-insights metrics show \
  --app "$APP_INSIGHTS_NAME" \
  --resource-group rg_ACD \
  --metric "requests/duration" \
  --aggregation avg
```

**Enable detailed tracing:**
```bash
az containerapp update \
  --name orchestrator \
  --resource-group rg_ACD \
  --set-env-vars LOG_LEVEL=DEBUG
```

---

## Clean Up

### Delete All Resources

**⚠️ WARNING: This will permanently delete all data!**

```bash
az group delete --name rg_ACD --yes --no-wait
```

### Delete Specific Resources

```bash
# Delete Container App only
az containerapp delete --name orchestrator --resource-group rg_ACD --yes

# Delete Cosmos DB only
az cosmosdb delete --name "$COSMOS_ACCOUNT" --resource-group rg_ACD --yes

# Delete Container Registry only
az acr delete --name acracddev --resource-group rg_ACD --yes
```

---

## Next Steps

After successful deployment:

1. ✅ **Test OAuth flows** with real providers
2. ✅ **Create a test connection** in the UI (bind Azure subscription)
3. ✅ **Run a discovery** (inventory/cost/security tier)
4. ✅ **Monitor Application Insights** for errors
5. 🔄 **Set up CI/CD** (GitHub Actions for automated deployments)
6. 🔄 **Configure custom domain** (optional)
7. 🔄 **Enable APIM** for external Azure API routing (Phase 3 extension)
8. 🔄 **Add AI Search** for knowledge services (Phase 4)

## Support

- **Issues:** [GitHub Issues](https://github.com/your-org/agentic-cloud-disc/issues)
- **Docs:** [Architecture Documentation](./docs/architecture/)
- **Slack:** #agentic-cloud-disc (internal)

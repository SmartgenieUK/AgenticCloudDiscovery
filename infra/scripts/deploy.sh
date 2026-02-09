#!/bin/bash
set -e

# AgenticCloudDisc Deployment Script
# Usage: ./deploy.sh [dev|prod]

ENVIRONMENT=${1:-dev}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$INFRA_DIR")"

echo "🚀 Deploying AgenticCloudDisc to $ENVIRONMENT environment..."

# Load configuration
if [ "$ENVIRONMENT" = "dev" ]; then
    RESOURCE_GROUP="rg_ACD"
    LOCATION="eastus"
    REGISTRY_NAME="acracddev"
else
    echo "❌ Only 'dev' environment is configured. Please update script for prod deployment."
    exit 1
fi

# Verify Azure CLI is logged in
echo "📋 Verifying Azure CLI authentication..."
az account show > /dev/null 2>&1 || {
    echo "❌ Not logged in to Azure. Please run 'az login' first."
    exit 1
}

# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "✅ Using subscription: $SUBSCRIPTION_ID"

# Create resource group if it doesn't exist
echo "📦 Ensuring resource group exists..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
echo "✅ Resource group ready: $RESOURCE_GROUP"

# Create Azure Container Registry if it doesn't exist
echo "🐳 Setting up Azure Container Registry..."
ACR_EXISTS=$(az acr show --name "$REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null || echo "notfound")
if [ "$ACR_EXISTS" = "notfound" ]; then
    echo "Creating new ACR: $REGISTRY_NAME"
    az acr create \
        --name "$REGISTRY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --sku Basic \
        --admin-enabled true \
        --output none
fi

# Get ACR credentials
echo "🔑 Retrieving ACR credentials..."
ACR_SERVER=$(az acr show --name "$REGISTRY_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$REGISTRY_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$REGISTRY_NAME" --query passwords[0].value -o tsv)
echo "✅ ACR ready: $ACR_SERVER"

# Build and push Docker images
echo "🏗️  Building and pushing Docker images..."

# Build MCP Server
echo "  📦 Building mcp-server..."
cd "$ROOT_DIR/mcp-server"
docker build -t "$ACR_SERVER/agentic-cloud-disc/mcp-server:latest" .
docker push "$ACR_SERVER/agentic-cloud-disc/mcp-server:latest"
echo "  ✅ mcp-server pushed"

# Build Orchestrator
echo "  📦 Building orchestrator..."
cd "$ROOT_DIR/agent-orchestrator"
docker build -t "$ACR_SERVER/agentic-cloud-disc/orchestrator:latest" .
docker push "$ACR_SERVER/agentic-cloud-disc/orchestrator:latest"
echo "  ✅ orchestrator pushed"

# Build Client UI
echo "  📦 Building client-ui..."
cd "$ROOT_DIR/client-ui"
docker build -t "$ACR_SERVER/agentic-cloud-disc/client-ui:latest" .
docker push "$ACR_SERVER/agentic-cloud-disc/client-ui:latest"
echo "  ✅ client-ui pushed"

# Generate JWT secret if not exists
echo "🔐 Checking JWT secret..."
JWT_SECRET=$(openssl rand -base64 32 | tr -d '\n')

# Create or update Key Vault for secrets
KV_NAME="kv-acd-${ENVIRONMENT}-temp"
echo "🔑 Setting up Key Vault: $KV_NAME..."

# Delete existing Key Vault if it exists (for dev only)
if [ "$ENVIRONMENT" = "dev" ]; then
    az keyvault delete --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null || true
    az keyvault purge --name "$KV_NAME" 2>/dev/null || true
fi

# Create Key Vault
az keyvault create \
    --name "$KV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --enable-rbac-authorization false \
    --output none

# Set secrets
echo "  📝 Storing secrets..."
az keyvault secret set --vault-name "$KV_NAME" --name "acr-password" --value "$ACR_PASSWORD" --output none
az keyvault secret set --vault-name "$KV_NAME" --name "jwt-secret-key" --value "$JWT_SECRET" --output none

# Placeholder OAuth secrets (replace with real values)
az keyvault secret set --vault-name "$KV_NAME" --name "google-client-secret" --value "placeholder-google-secret" --output none
az keyvault secret set --vault-name "$KV_NAME" --name "microsoft-client-secret" --value "placeholder-microsoft-secret" --output none

echo "✅ Secrets stored in Key Vault"

# Get current user principal ID for Key Vault access
PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv)

# Update parameters file with actual values
PARAMS_FILE="$INFRA_DIR/parameters/${ENVIRONMENT}.parameters.json"
TEMP_PARAMS_FILE=$(mktemp)

cat > "$TEMP_PARAMS_FILE" <<EOF
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "environment": {
      "value": "$ENVIRONMENT"
    },
    "location": {
      "value": "$LOCATION"
    },
    "containerRegistryServer": {
      "value": "$ACR_SERVER"
    },
    "containerRegistryUsername": {
      "value": "$ACR_USERNAME"
    },
    "containerRegistryPassword": {
      "value": "$ACR_PASSWORD"
    },
    "jwtSecretKey": {
      "value": "$JWT_SECRET"
    },
    "googleClientId": {
      "value": "placeholder-google-client-id"
    },
    "googleClientSecret": {
      "value": "placeholder-google-secret"
    },
    "microsoftClientId": {
      "value": "placeholder-microsoft-client-id"
    },
    "microsoftClientSecret": {
      "value": "placeholder-microsoft-secret"
    },
    "principalId": {
      "value": "$PRINCIPAL_ID"
    }
  }
}
EOF

# Deploy infrastructure
echo "☁️  Deploying Azure infrastructure..."
cd "$INFRA_DIR"

DEPLOYMENT_NAME="agentic-cloud-disc-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
az deployment group create \
    --name "$DEPLOYMENT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --template-file main.bicep \
    --parameters "@${TEMP_PARAMS_FILE}" \
    --output json > deployment-output.json

# Clean up temp file
rm "$TEMP_PARAMS_FILE"

# Extract outputs
echo "📊 Deployment complete! Extracting outputs..."
COSMOS_ENDPOINT=$(jq -r '.properties.outputs.cosmosEndpoint.value' deployment-output.json)
ORCHESTRATOR_URL=$(jq -r '.properties.outputs.orchestratorUrl.value' deployment-output.json)
CLIENT_UI_URL=$(jq -r '.properties.outputs.clientUiUrl.value' deployment-output.json)

echo ""
echo "========================================="
echo "🎉 Deployment Successful!"
echo "========================================="
echo "Environment: $ENVIRONMENT"
echo "Resource Group: $RESOURCE_GROUP"
echo ""
echo "📍 URLs:"
echo "  Client UI:     $CLIENT_UI_URL"
echo "  Orchestrator:  $ORCHESTRATOR_URL"
echo ""
echo "📦 Resources:"
echo "  Cosmos DB:     $COSMOS_ENDPOINT"
echo "  Container Registry: $ACR_SERVER"
echo ""
echo "🔍 Next Steps:"
echo "  1. Run seed-data.sh to populate Cosmos DB with initial data"
echo "  2. Update OAuth client secrets in Key Vault"
echo "  3. Test the deployment at: $CLIENT_UI_URL"
echo "========================================="

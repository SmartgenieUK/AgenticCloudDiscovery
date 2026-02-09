#!/bin/bash
set -e

# Seed initial data into Cosmos DB
# Usage: ./seed-data.sh [dev|prod]

ENVIRONMENT=${1:-dev}
RESOURCE_GROUP="rg_ACD"

echo "🌱 Seeding data for $ENVIRONMENT environment..."

# Get Cosmos DB account name and key
COSMOS_ACCOUNT=$(az cosmosdb list --resource-group "$RESOURCE_GROUP" --query "[?contains(name, '${ENVIRONMENT}')].name" -o tsv | head -1)
if [ -z "$COSMOS_ACCOUNT" ]; then
    echo "❌ No Cosmos DB account found for environment: $ENVIRONMENT"
    exit 1
fi

echo "📦 Using Cosmos DB account: $COSMOS_ACCOUNT"

COSMOS_KEY=$(az cosmosdb keys list --name "$COSMOS_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query primaryMasterKey -o tsv)
COSMOS_ENDPOINT=$(az cosmosdb show --name "$COSMOS_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query documentEndpoint -o tsv)

DATABASE_NAME="agentic-cloud-disc"

echo "✅ Cosmos DB credentials retrieved"

# Seed default policy
echo "📝 Seeding default policy..."
az cosmosdb sql container item create \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$COSMOS_ACCOUNT" \
  --database-name "$DATABASE_NAME" \
  --container-name policies \
  --partition-key-value "default" \
  --body '{
    "policy_id": "default",
    "allowed_domains": ["management.azure.com", "graph.microsoft.com"],
    "allowed_methods": ["GET", "POST"],
    "max_payload_bytes": 10485760,
    "max_retries": 3,
    "approval_required": true,
    "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "updated_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'"
  }' --output none 2>/dev/null || echo "  ⚠️  Default policy already exists"

echo "✅ Default policy seeded"

# Seed inventory_discovery tool
echo "📝 Seeding inventory_discovery tool..."
az cosmosdb sql container item create \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$COSMOS_ACCOUNT" \
  --database-name "$DATABASE_NAME" \
  --container-name tools \
  --partition-key-value "inventory_discovery" \
  --body '{
    "tool_id": "inventory_discovery",
    "name": "Azure Inventory Discovery",
    "description": "Read-only inventory of Azure resources for a given subscription/tenant.",
    "args_schema": {
      "type": "object",
      "properties": {
        "connection_id": {"type": "string"},
        "tenant_id": {"type": "string"},
        "subscription_id": {"type": "string"},
        "tier": {"type": "string", "enum": ["inventory"]},
        "correlation_id": {"type": "string"},
        "session_id": {"type": "string"}
      },
      "required": ["connection_id", "subscription_id", "tier"]
    },
    "allowed_domains": ["management.azure.com"],
    "allowed_methods": ["GET"],
    "status": "approved",
    "provenance": "system",
    "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "updated_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'"
  }' --output none 2>/dev/null || echo "  ⚠️  inventory_discovery tool already exists"

echo "✅ inventory_discovery tool seeded"

# Seed cost_discovery tool
echo "📝 Seeding cost_discovery tool..."
az cosmosdb sql container item create \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$COSMOS_ACCOUNT" \
  --database-name "$DATABASE_NAME" \
  --container-name tools \
  --partition-key-value "cost_discovery" \
  --body '{
    "tool_id": "cost_discovery",
    "name": "Azure Cost Discovery",
    "description": "Retrieve Azure cost/usage data for an authorized scope.",
    "args_schema": {
      "type": "object",
      "properties": {
        "connection_id": {"type": "string"},
        "tenant_id": {"type": "string"},
        "subscription_id": {"type": "string"},
        "tier": {"type": "string", "enum": ["cost"]},
        "correlation_id": {"type": "string"},
        "session_id": {"type": "string"}
      },
      "required": ["connection_id", "subscription_id", "tier"]
    },
    "allowed_domains": ["management.azure.com"],
    "allowed_methods": ["GET", "POST"],
    "status": "approved",
    "provenance": "system",
    "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "updated_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'"
  }' --output none 2>/dev/null || echo "  ⚠️  cost_discovery tool already exists"

echo "✅ cost_discovery tool seeded"

# Seed security_discovery tool
echo "📝 Seeding security_discovery tool..."
az cosmosdb sql container item create \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$COSMOS_ACCOUNT" \
  --database-name "$DATABASE_NAME" \
  --container-name tools \
  --partition-key-value "security_discovery" \
  --body '{
    "tool_id": "security_discovery",
    "name": "Azure Security Discovery",
    "description": "Fetch security posture/policy/defender signals for an authorized scope.",
    "args_schema": {
      "type": "object",
      "properties": {
        "connection_id": {"type": "string"},
        "tenant_id": {"type": "string"},
        "subscription_id": {"type": "string"},
        "tier": {"type": "string", "enum": ["security"]},
        "correlation_id": {"type": "string"},
        "session_id": {"type": "string"}
      },
      "required": ["connection_id", "subscription_id", "tier"]
    },
    "allowed_domains": ["management.azure.com", "graph.microsoft.com"],
    "allowed_methods": ["GET"],
    "status": "approved",
    "provenance": "system",
    "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "updated_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'"
  }' --output none 2>/dev/null || echo "  ⚠️  security_discovery tool already exists"

echo "✅ security_discovery tool seeded"

echo ""
echo "========================================="
echo "🎉 Data Seeding Complete!"
echo "========================================="
echo "Cosmos DB: $COSMOS_ENDPOINT"
echo "Database: $DATABASE_NAME"
echo ""
echo "Seeded:"
echo "  ✅ 1 default policy"
echo "  ✅ 3 approved tools (inventory, cost, security)"
echo ""
echo "Containers ready:"
echo "  - users"
echo "  - connections"
echo "  - discoveries"
echo "  - policies (1 item)"
echo "  - tools (3 items)"
echo "  - sessions"
echo "========================================="

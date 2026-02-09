#!/bin/bash

# ============================================================================
# Azure Setup Script for Agentic Cloud Discovery MVP (Bash version)
# ============================================================================
# This script sets up all required Azure resources for the MVP deployment
# Run this BEFORE deploying the Bicep templates (Phase 3)
#
# Prerequisites:
#   - Azure CLI installed (az --version)
#   - Logged in to Azure (az login)
#   - Owner or Contributor role on subscription
# ============================================================================

set -e  # Exit on error

# Default values
SUBSCRIPTION_ID="${1:-}"
RESOURCE_GROUP_NAME="${2:-rg-agentic-cloud-disc-dev}"
LOCATION="${3:-eastus}"
ENVIRONMENT="${4:-dev}"

# Color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function success() { echo -e "${GREEN}✅ $1${NC}"; }
function info() { echo -e "${CYAN}ℹ️  $1${NC}"; }
function warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
function error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

info "=================================================="
info "Azure Setup for Agentic Cloud Discovery MVP"
info "=================================================="
echo ""

# Step 1: Check Azure CLI installation
info "Step 1: Checking Azure CLI installation..."
if command -v az &> /dev/null; then
    AZ_VERSION=$(az --version | head -n 1)
    success "Azure CLI is installed: $AZ_VERSION"
else
    error "Azure CLI is not installed. Please install from: https://aka.ms/install-azure-cli"
fi

# Step 2: Check login status
info "Step 2: Checking Azure login status..."
if ! az account show &> /dev/null; then
    warning "Not logged in to Azure. Running 'az login'..."
    az login || error "Failed to log in to Azure"
fi
success "Logged in to Azure"

# Step 3: Set subscription
if [ -z "$SUBSCRIPTION_ID" ]; then
    info "Step 3: Using current subscription..."
    CURRENT_SUB=$(az account show --query "name" -o tsv)
    info "Current subscription: $CURRENT_SUB"
else
    info "Step 3: Setting subscription to $SUBSCRIPTION_ID..."
    az account set --subscription "$SUBSCRIPTION_ID" || error "Failed to set subscription"
    success "Subscription set"
fi

SUB_ID=$(az account show --query "id" -o tsv)
info "Subscription ID: $SUB_ID"

# Step 4: Create resource group
info "Step 4: Creating resource group '$RESOURCE_GROUP_NAME' in '$LOCATION'..."
az group create --name "$RESOURCE_GROUP_NAME" --location "$LOCATION" --output none
success "Resource group created/verified"

# Step 5: Register resource providers
info "Step 5: Registering Azure resource providers (this may take a few minutes)..."
PROVIDERS=(
    "Microsoft.App"
    "Microsoft.ContainerRegistry"
    "Microsoft.OperationalInsights"
    "Microsoft.DocumentDB"
    "Microsoft.ApiManagement"
    "Microsoft.KeyVault"
    "Microsoft.Search"
    "Microsoft.CognitiveServices"
)

for PROVIDER in "${PROVIDERS[@]}"; do
    info "  Registering $PROVIDER..."
    if az provider register --namespace "$PROVIDER" --wait; then
        success "  $PROVIDER registered"
    else
        warning "  Failed to register $PROVIDER (may already be registered)"
    fi
done

# Step 6: Create Key Vault for secrets
KEY_VAULT_NAME="kv-acd-$ENVIRONMENT-$RANDOM"
info "Step 6: Creating Key Vault '$KEY_VAULT_NAME'..."
if az keyvault create \
    --name "$KEY_VAULT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --enable-rbac-authorization true \
    --output none; then
    success "Key Vault created: $KEY_VAULT_NAME"
else
    warning "Key Vault creation failed (may already exist)"
fi

# Step 7: Get current user object ID for Key Vault access
info "Step 7: Configuring Key Vault access..."
CURRENT_USER_ID=$(az ad signed-in-user show --query id -o tsv)
KEY_VAULT_ID=$(az keyvault show --name "$KEY_VAULT_NAME" --resource-group "$RESOURCE_GROUP_NAME" --query id -o tsv)

# Assign Key Vault Secrets Officer role to current user
if az role assignment create \
    --role "Key Vault Secrets Officer" \
    --assignee "$CURRENT_USER_ID" \
    --scope "$KEY_VAULT_ID" \
    --output none; then
    success "Key Vault access configured for current user"
else
    warning "Failed to assign Key Vault role (you may need Owner permissions)"
fi

# Step 8: Create storage account for Bicep state (optional but recommended)
STORAGE_ACCOUNT_NAME="stacd$ENVIRONMENT$RANDOM"
info "Step 8: Creating storage account for deployment state (optional)..."
if az storage account create \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --output none; then
    success "Storage account created: $STORAGE_ACCOUNT_NAME"
else
    warning "Storage account creation failed (not critical)"
fi

# Step 9: Output configuration summary
echo ""
info "=================================================="
info "Setup Complete! Configuration Summary:"
info "=================================================="
success "Resource Group: $RESOURCE_GROUP_NAME"
success "Location: $LOCATION"
success "Subscription ID: $SUB_ID"
success "Key Vault: $KEY_VAULT_NAME"
success "Storage Account: $STORAGE_ACCOUNT_NAME"
echo ""

# Step 10: Save configuration to file
CONFIG_FILE="infra/config/$ENVIRONMENT-config.json"
info "Step 10: Saving configuration to $CONFIG_FILE..."

mkdir -p infra/config
cat > "$CONFIG_FILE" <<EOF
{
  "subscriptionId": "$SUB_ID",
  "resourceGroupName": "$RESOURCE_GROUP_NAME",
  "location": "$LOCATION",
  "environment": "$ENVIRONMENT",
  "keyVaultName": "$KEY_VAULT_NAME",
  "storageAccountName": "$STORAGE_ACCOUNT_NAME",
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

success "Configuration saved to $CONFIG_FILE"

echo ""
info "=================================================="
info "Next Steps:"
info "=================================================="
info "1. Configure OAuth applications (see oauth-setup-guide.md)"
info "2. Store OAuth secrets in Key Vault using store-secrets.sh"
info "3. Run Bicep deployment (Phase 3) using deploy.sh"
echo ""
success "Azure setup complete! ✅"

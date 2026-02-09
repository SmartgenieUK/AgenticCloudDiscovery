# ============================================================================
# Azure Setup Script for Agentic Cloud Discovery MVP
# ============================================================================
# This script sets up all required Azure resources for the MVP deployment
# Run this BEFORE deploying the Bicep templates (Phase 3)
#
# Prerequisites:
#   - Azure CLI installed (az --version)
#   - Logged in to Azure (az login)
#   - Owner or Contributor role on subscription
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId = "",

    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName = "rg-agentic-cloud-disc-dev",

    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",

    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev"
)

# Color functions for output
function Write-Success { Write-Host "✅ $args" -ForegroundColor Green }
function Write-Info { Write-Host "ℹ️  $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "❌ $args" -ForegroundColor Red }

Write-Info "=================================================="
Write-Info "Azure Setup for Agentic Cloud Discovery MVP"
Write-Info "=================================================="
Write-Info ""

# Step 1: Check Azure CLI installation
Write-Info "Step 1: Checking Azure CLI installation..."
try {
    $azVersion = az --version 2>&1 | Select-String "azure-cli" | Out-String
    Write-Success "Azure CLI is installed: $($azVersion.Trim())"
} catch {
    Write-Error "Azure CLI is not installed. Please install from: https://aka.ms/install-azure-cli"
    exit 1
}

# Step 2: Check login status
Write-Info "Step 2: Checking Azure login status..."
$account = az account show 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Not logged in to Azure. Running 'az login'..."
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to log in to Azure"
        exit 1
    }
}
Write-Success "Logged in to Azure"

# Step 3: Set subscription
if ($SubscriptionId -eq "") {
    Write-Info "Step 3: Using current subscription..."
    $currentSub = az account show --query "name" -o tsv
    Write-Info "Current subscription: $currentSub"
} else {
    Write-Info "Step 3: Setting subscription to $SubscriptionId..."
    az account set --subscription $SubscriptionId
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to set subscription"
        exit 1
    }
    Write-Success "Subscription set"
}

$subId = az account show --query "id" -o tsv
Write-Info "Subscription ID: $subId"

# Step 4: Create resource group
Write-Info "Step 4: Creating resource group '$ResourceGroupName' in '$Location'..."
az group create --name $ResourceGroupName --location $Location --output none
if ($LASTEXITCODE -eq 0) {
    Write-Success "Resource group created/verified"
} else {
    Write-Error "Failed to create resource group"
    exit 1
}

# Step 5: Register resource providers
Write-Info "Step 5: Registering Azure resource providers (this may take a few minutes)..."
$providers = @(
    "Microsoft.App",
    "Microsoft.ContainerRegistry",
    "Microsoft.OperationalInsights",
    "Microsoft.DocumentDB",
    "Microsoft.ApiManagement",
    "Microsoft.KeyVault",
    "Microsoft.Search",
    "Microsoft.CognitiveServices"
)

foreach ($provider in $providers) {
    Write-Info "  Registering $provider..."
    az provider register --namespace $provider --wait
    if ($LASTEXITCODE -eq 0) {
        Write-Success "  $provider registered"
    } else {
        Write-Warning "  Failed to register $provider (may already be registered)"
    }
}

# Step 6: Create Key Vault for secrets
$keyVaultName = "kv-acd-$Environment-$(Get-Random -Maximum 9999)"
Write-Info "Step 6: Creating Key Vault '$keyVaultName'..."
az keyvault create `
    --name $keyVaultName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --enable-rbac-authorization true `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Key Vault created: $keyVaultName"
} else {
    Write-Warning "Key Vault creation failed (may already exist)"
}

# Step 7: Get current user object ID for Key Vault access
Write-Info "Step 7: Configuring Key Vault access..."
$currentUserId = az ad signed-in-user show --query id -o tsv
$keyVaultId = az keyvault show --name $keyVaultName --resource-group $ResourceGroupName --query id -o tsv

# Assign Key Vault Secrets Officer role to current user
az role assignment create `
    --role "Key Vault Secrets Officer" `
    --assignee $currentUserId `
    --scope $keyVaultId `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Key Vault access configured for current user"
} else {
    Write-Warning "Failed to assign Key Vault role (you may need Owner permissions)"
}

# Step 8: Create storage account for Bicep state (optional but recommended)
$storageAccountName = "stacd$Environment$(Get-Random -Maximum 99999)"
Write-Info "Step 8: Creating storage account for deployment state (optional)..."
az storage account create `
    --name $storageAccountName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --sku Standard_LRS `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Storage account created: $storageAccountName"
} else {
    Write-Warning "Storage account creation failed (not critical)"
}

# Step 9: Output configuration summary
Write-Info ""
Write-Info "=================================================="
Write-Info "Setup Complete! Configuration Summary:"
Write-Info "=================================================="
Write-Success "Resource Group: $ResourceGroupName"
Write-Success "Location: $Location"
Write-Success "Subscription ID: $subId"
Write-Success "Key Vault: $keyVaultName"
Write-Success "Storage Account: $storageAccountName"
Write-Info ""

# Step 10: Save configuration to file
$configFile = "infra\config\$Environment-config.json"
Write-Info "Step 10: Saving configuration to $configFile..."

$config = @{
    subscriptionId = $subId
    resourceGroupName = $ResourceGroupName
    location = $Location
    environment = $Environment
    keyVaultName = $keyVaultName
    storageAccountName = $storageAccountName
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}

New-Item -ItemType Directory -Force -Path "infra\config" | Out-Null
$config | ConvertTo-Json | Out-File -FilePath $configFile -Encoding UTF8
Write-Success "Configuration saved to $configFile"

Write-Info ""
Write-Info "=================================================="
Write-Info "Next Steps:"
Write-Info "=================================================="
Write-Info "1. Configure OAuth applications (see oauth-setup-guide.md)"
Write-Info "2. Store OAuth secrets in Key Vault using store-secrets.ps1"
Write-Info "3. Run Bicep deployment (Phase 3) using deploy.ps1"
Write-Info ""
Write-Success "Azure setup complete! ✅"

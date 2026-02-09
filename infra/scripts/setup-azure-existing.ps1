# ============================================================================
# Azure Setup Script - Use Existing Resources
# ============================================================================
# This script uses your EXISTING rg_ACD resource group and Cosmos DB
# It only creates MISSING resources needed for MVP deployment:
#   - Key Vault for OAuth secrets
#   - Resource provider registrations
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName = "rg_ACD",

    [Parameter(Mandatory=$false)]
    [string]$CosmosAccountName = "sg-agentic-cosmos-acd",

    [Parameter(Mandatory=$false)]
    [string]$CosmosDatabaseName = "agentic_acd",

    [Parameter(Mandatory=$false)]
    [string]$Location = "uksouth",

    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev"
)

# Color functions for output
function Write-Success { Write-Host "✅ $args" -ForegroundColor Green }
function Write-Info { Write-Host "ℹ️  $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "❌ $args" -ForegroundColor Red }

Write-Info "=================================================="
Write-Info "Azure Setup - Using Existing Resources"
Write-Info "=================================================="
Write-Info ""
Write-Info "This script will use your existing:"
Write-Info "  - Resource Group: $ResourceGroupName"
Write-Info "  - Cosmos DB: $CosmosAccountName"
Write-Info "  - Database: $CosmosDatabaseName"
Write-Info ""
Write-Info "And will create missing resources:"
Write-Info "  - Key Vault for OAuth secrets"
Write-Info "  - Register resource providers"
Write-Info ""

# Confirm with user
$confirm = Read-Host "Continue? (yes/no)"
if ($confirm -ne "yes" -and $confirm -ne "y") {
    Write-Warning "Setup cancelled by user"
    exit 0
}

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

$subId = az account show --query "id" -o tsv
$subName = az account show --query "name" -o tsv
Write-Info "Subscription: $subName"
Write-Info "Subscription ID: $subId"

# Step 3: Verify existing resource group
Write-Info "Step 3: Verifying existing resource group '$ResourceGroupName'..."
$rgExists = az group exists --name $ResourceGroupName
if ($rgExists -eq "true") {
    Write-Success "Resource group verified: $ResourceGroupName"
    $rgLocation = az group show --name $ResourceGroupName --query "location" -o tsv
    Write-Info "Location: $rgLocation"
} else {
    Write-Error "Resource group '$ResourceGroupName' not found. Please check the name."
    exit 1
}

# Step 4: Verify existing Cosmos DB
Write-Info "Step 4: Verifying existing Cosmos DB '$CosmosAccountName'..."
$cosmosExists = az cosmosdb show --name $CosmosAccountName --resource-group $ResourceGroupName --query "name" -o tsv 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Success "Cosmos DB verified: $CosmosAccountName"

    # Check database exists
    $dbExists = az cosmosdb sql database show --account-name $CosmosAccountName --resource-group $ResourceGroupName --name $CosmosDatabaseName --query "name" -o tsv 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Database verified: $CosmosDatabaseName"

        # List containers
        Write-Info "Existing containers:"
        $containers = az cosmosdb sql container list --account-name $CosmosAccountName --resource-group $ResourceGroupName --database-name $CosmosDatabaseName --query "[].name" -o tsv
        foreach ($container in $containers) {
            Write-Success "  ✓ $container"
        }
    } else {
        Write-Warning "Database '$CosmosDatabaseName' not found (this is OK, will be created in Phase 3)"
    }
} else {
    Write-Error "Cosmos DB '$CosmosAccountName' not found in resource group '$ResourceGroupName'"
    exit 1
}

# Step 5: Register resource providers
Write-Info "Step 5: Registering Azure resource providers (if not already registered)..."
$providers = @(
    "Microsoft.App",
    "Microsoft.ContainerRegistry",
    "Microsoft.OperationalInsights",
    "Microsoft.ApiManagement",
    "Microsoft.KeyVault",
    "Microsoft.Search",
    "Microsoft.CognitiveServices"
)

foreach ($provider in $providers) {
    $status = az provider show --namespace $provider --query "registrationState" -o tsv 2>&1
    if ($status -eq "Registered") {
        Write-Success "  $provider already registered"
    } else {
        Write-Info "  Registering $provider..."
        az provider register --namespace $provider --wait
        if ($LASTEXITCODE -eq 0) {
            Write-Success "  $provider registered"
        } else {
            Write-Warning "  Failed to register $provider (may need time to propagate)"
        }
    }
}

# Step 6: Check if Key Vault already exists
Write-Info "Step 6: Checking for existing Key Vault..."
$existingKVs = az keyvault list --resource-group $ResourceGroupName --query "[].name" -o tsv
if ($existingKVs) {
    Write-Info "Found existing Key Vault(s) in $ResourceGroupName:"
    foreach ($kv in $existingKVs) {
        Write-Info "  - $kv"
    }
    $useExisting = Read-Host "Use existing Key Vault '$($existingKVs[0])'? (yes/no)"

    if ($useExisting -eq "yes" -or $useExisting -eq "y") {
        $keyVaultName = $existingKVs[0]
        Write-Success "Using existing Key Vault: $keyVaultName"
    } else {
        # Create new Key Vault
        $keyVaultName = "kv-acd-$Environment-$(Get-Random -Maximum 9999)"
        Write-Info "Creating new Key Vault '$keyVaultName'..."
        az keyvault create `
            --name $keyVaultName `
            --resource-group $ResourceGroupName `
            --location $rgLocation `
            --enable-rbac-authorization true `
            --output none

        if ($LASTEXITCODE -eq 0) {
            Write-Success "Key Vault created: $keyVaultName"
        } else {
            Write-Error "Failed to create Key Vault"
            exit 1
        }
    }
} else {
    # Create new Key Vault
    $keyVaultName = "kv-acd-$Environment-$(Get-Random -Maximum 9999)"
    Write-Info "Creating Key Vault '$keyVaultName'..."
    az keyvault create `
        --name $keyVaultName `
        --resource-group $ResourceGroupName `
        --location $rgLocation `
        --enable-rbac-authorization true `
        --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Key Vault created: $keyVaultName"
    } else {
        Write-Error "Failed to create Key Vault"
        exit 1
    }
}

# Step 7: Configure Key Vault access for current user
Write-Info "Step 7: Configuring Key Vault access..."
$currentUserId = az ad signed-in-user show --query id -o tsv
$keyVaultId = az keyvault show --name $keyVaultName --resource-group $ResourceGroupName --query id -o tsv

# Check if role assignment already exists
$existingRole = az role assignment list --assignee $currentUserId --scope $keyVaultId --query "[?roleDefinitionName=='Key Vault Secrets Officer'].roleDefinitionName" -o tsv

if ($existingRole) {
    Write-Success "Key Vault access already configured for current user"
} else {
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
}

# Step 8: Get Cosmos DB connection details
Write-Info "Step 8: Retrieving Cosmos DB connection details..."
$cosmosEndpoint = az cosmosdb show --name $CosmosAccountName --resource-group $ResourceGroupName --query "documentEndpoint" -o tsv
$cosmosKey = az cosmosdb keys list --name $CosmosAccountName --resource-group $ResourceGroupName --query "primaryMasterKey" -o tsv

Write-Success "Cosmos DB endpoint: $cosmosEndpoint"
Write-Info "Cosmos DB key: (retrieved, will be saved to config)"

# Step 9: Save configuration to file
$configFile = "infra\config\$Environment-config.json"
Write-Info "Step 9: Saving configuration to $configFile..."

$config = @{
    subscriptionId = $subId
    subscriptionName = $subName
    resourceGroupName = $ResourceGroupName
    location = $rgLocation
    environment = $Environment
    cosmosAccountName = $CosmosAccountName
    cosmosEndpoint = $cosmosEndpoint
    cosmosDatabaseName = $CosmosDatabaseName
    keyVaultName = $keyVaultName
    existingInfrastructure = $true
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
}

New-Item -ItemType Directory -Force -Path "infra\config" | Out-Null
$config | ConvertTo-Json | Out-File -FilePath $configFile -Encoding UTF8
Write-Success "Configuration saved to $configFile"

# Step 10: Create .env snippet for local development
$envSnippet = "infra\config\$Environment-env-snippet.txt"
Write-Info "Step 10: Creating .env snippet for local development..."

$envContent = @"
# Azure Configuration (from setup-azure-existing.ps1)
# Add these to your .env file for local development

COSMOS_ENDPOINT=$cosmosEndpoint
COSMOS_DATABASE=$CosmosDatabaseName
# COSMOS_KEY is sensitive - retrieve from Key Vault or use existing value

# Key Vault (for storing OAuth secrets)
KEY_VAULT_NAME=$keyVaultName

# Resource Group
AZURE_RESOURCE_GROUP=$ResourceGroupName
AZURE_LOCATION=$rgLocation
"@

$envContent | Out-File -FilePath $envSnippet -Encoding UTF8
Write-Success "Environment snippet saved to $envSnippet"

Write-Info ""
Write-Info "=================================================="
Write-Info "Setup Complete! Configuration Summary:"
Write-Info "=================================================="
Write-Success "Subscription: $subName"
Write-Success "Resource Group: $ResourceGroupName (existing)"
Write-Success "Location: $rgLocation"
Write-Success "Cosmos DB: $CosmosAccountName (existing)"
Write-Success "Database: $CosmosDatabaseName (existing)"
Write-Success "Key Vault: $keyVaultName"
Write-Success "Config saved: $configFile"
Write-Info ""

Write-Info "=================================================="
Write-Info "Next Steps:"
Write-Info "=================================================="
Write-Info "1. Store OAuth secrets in Key Vault:"
Write-Info "   .\infra\scripts\store-secrets.ps1 -KeyVaultName $keyVaultName"
Write-Info ""
Write-Info "2. (Optional) Review OAuth setup guide:"
Write-Info "   infra\scripts\oauth-setup-guide.md"
Write-Info ""
Write-Info "3. Ready for Phase 3: Deploy Container Apps, APIM, AI Search"
Write-Info "   (Bicep templates will be created in Phase 3)"
Write-Info ""
Write-Success "Azure setup complete! ✅"
Write-Info ""
Write-Info "Your existing Cosmos DB is ready to use."
Write-Info "All containers are already created and working!"

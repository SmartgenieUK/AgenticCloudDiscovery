# Azure Setup Guide for Agentic Cloud Discovery

This guide walks you through setting up the Azure infrastructure needed for the MVP deployment.

## Overview

You'll complete these steps in order:
1. ✅ **Basic Azure Setup** - Resource group, providers, Key Vault
2. ✅ **OAuth Configuration** - Google and Microsoft OAuth apps
3. ✅ **Store Secrets** - Save OAuth credentials to Key Vault
4. ⏭️ **Deploy Infrastructure** - Run Bicep templates (Phase 3)

**Estimated Time**: 30-45 minutes

---

## Prerequisites

Before you begin, ensure you have:

- ✅ **Azure Subscription** with Owner or Contributor role
- ✅ **Azure CLI** installed ([Download](https://aka.ms/install-azure-cli))
- ✅ **Logged into Azure**: Run `az login`
- ✅ **PowerShell 7+** (Windows) or **Bash** (Mac/Linux)

**Verify your setup:**
```powershell
# Check Azure CLI version
az --version

# Check you're logged in
az account show

# Check current subscription
az account list --output table
```

---

## Step 1: Run Azure Setup Script

This script creates the resource group, registers providers, and sets up Key Vault.

### Option A: PowerShell (Recommended for Windows)

```powershell
# Run from project root
cd c:\LocalCode\AgenticCloudDisc

# Make script executable (if needed)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Run setup script
.\infra\scripts\setup-azure.ps1
```

**Optional parameters:**
```powershell
# Use specific subscription
.\infra\scripts\setup-azure.ps1 -SubscriptionId "your-sub-id"

# Change resource group name or location
.\infra\scripts\setup-azure.ps1 `
    -ResourceGroupName "rg-acd-production" `
    -Location "westus2" `
    -Environment "prod"
```

### Option B: Bash (Mac/Linux or WSL)

```bash
# Run from project root
cd /c/LocalCode/AgenticCloudDisc

# Make script executable
chmod +x infra/scripts/setup-azure.sh

# Run setup script
./infra/scripts/setup-azure.sh
```

**Optional parameters:**
```bash
# Use specific subscription, resource group, location, environment
./infra/scripts/setup-azure.sh "your-sub-id" "rg-acd-production" "westus2" "prod"
```

### What This Script Does

1. ✅ Verifies Azure CLI is installed and you're logged in
2. ✅ Creates resource group (default: `rg-agentic-cloud-disc-dev`)
3. ✅ Registers Azure resource providers:
   - Microsoft.App (Container Apps)
   - Microsoft.DocumentDB (Cosmos DB)
   - Microsoft.ApiManagement (APIM)
   - Microsoft.KeyVault
   - Microsoft.Search (AI Search)
   - Microsoft.CognitiveServices (Azure OpenAI, Document Intelligence)
4. ✅ Creates Key Vault for secrets
5. ✅ Assigns you Key Vault Secrets Officer role
6. ✅ Creates storage account for deployment state
7. ✅ Saves configuration to `infra/config/dev-config.json`

### Expected Output

```
✅ Azure CLI is installed
✅ Logged in to Azure
ℹ️  Subscription ID: abc-123-def-456
✅ Resource group created/verified
✅ All resource providers registered
✅ Key Vault created: kv-acd-dev-1234
✅ Configuration saved to infra/config/dev-config.json
✅ Azure setup complete! ✅
```

**⏱️ Estimated time**: 5-10 minutes (provider registration takes longest)

---

## Step 2: Configure OAuth Applications

Follow the detailed guide to set up Google and Microsoft OAuth:

📖 **[OAuth Setup Guide](scripts/oauth-setup-guide.md)**

### Quick Summary

**Google OAuth:**
1. Create project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google+ API
3. Configure OAuth consent screen
4. Create OAuth client ID
5. Add redirect URI: `http://localhost:8000/auth/oauth/google/callback`
6. Copy Client ID and Client Secret

**Microsoft OAuth:**
1. Register app in [Azure Portal](https://portal.azure.com/) → Azure AD → App registrations
2. Add redirect URI: `http://localhost:8000/auth/oauth/microsoft/callback`
3. Create client secret
4. Copy Application ID and Client Secret

**⏱️ Estimated time**: 15-20 minutes

---

## Step 3: Store Secrets in Key Vault

Once you have your OAuth credentials, store them securely:

```powershell
# Run the store-secrets script
.\infra\scripts\store-secrets.ps1
```

The script will prompt you for:
- Google Client ID
- Google Client Secret
- Microsoft Client ID
- Microsoft Client Secret

It will also generate a secure `AUTH_SECRET_KEY` automatically.

### What Gets Stored

| Secret Name | Description |
|-------------|-------------|
| `google-client-id` | Google OAuth client ID |
| `google-client-secret` | Google OAuth client secret |
| `microsoft-client-id` | Microsoft OAuth application ID |
| `microsoft-client-secret` | Microsoft OAuth client secret |
| `auth-secret-key` | JWT signing key (auto-generated) |

**⏱️ Estimated time**: 2 minutes

---

## Step 4: Update Local .env for Development

For local development (before Azure deployment), update your `.env` file:

```bash
# OAuth credentials (use the same values you stored in Key Vault)
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/oauth/google/callback

MICROSOFT_CLIENT_ID=<your-microsoft-client-id>
MICROSOFT_CLIENT_SECRET=<your-microsoft-client-secret>
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/oauth/microsoft/callback
```

**Note**: In production (Phase 3), the Bicep templates will automatically pull secrets from Key Vault, so you won't need environment variables.

---

## Verification Checklist

Before proceeding to Phase 3, verify:

- ✅ Azure resource group exists
- ✅ Key Vault created and accessible
- ✅ Google OAuth app configured
- ✅ Microsoft OAuth app configured
- ✅ All secrets stored in Key Vault
- ✅ Local `.env` file updated

**Verify in Azure Portal:**
```
1. Navigate to your resource group (e.g., rg-agentic-cloud-disc-dev)
2. You should see:
   - Key Vault (kv-acd-dev-XXXX)
   - Storage account (stacddevXXXXX)
3. Open Key Vault → Secrets → Verify 5 secrets are present
```

**Verify locally:**
```powershell
# Test orchestrator can start with OAuth config
cd agent-orchestrator
uvicorn main:app --reload --port 8000

# You should see no errors about missing OAuth config
# Press Ctrl+C to stop
```

---

## Configuration Files Created

After setup, you'll have:

```
infra/
├── config/
│   └── dev-config.json          # Your Azure resource names and IDs
└── scripts/
    ├── setup-azure.ps1          # Setup script (PowerShell)
    ├── setup-azure.sh           # Setup script (Bash)
    ├── store-secrets.ps1        # Secret storage script
    └── oauth-setup-guide.md     # Detailed OAuth guide
```

**Example `dev-config.json`:**
```json
{
  "subscriptionId": "abc-123-def-456",
  "resourceGroupName": "rg-agentic-cloud-disc-dev",
  "location": "eastus",
  "environment": "dev",
  "keyVaultName": "kv-acd-dev-1234",
  "storageAccountName": "stacddev12345",
  "timestamp": "2026-02-08 22:45:00"
}
```

---

## Troubleshooting

### Common Issues

**"Insufficient privileges to complete the operation"**
- Solution: Ensure you have Owner or Contributor role on the subscription
- Check: `az role assignment list --assignee $(az ad signed-in-user show --query id -o tsv) --subscription $(az account show --query id -o tsv)`

**"The subscription is not registered to use namespace 'Microsoft.App'"**
- Solution: Wait a few minutes for provider registration to complete
- Or manually register: `az provider register --namespace Microsoft.App --wait`

**"Key Vault name is already taken"**
- Solution: Key Vault names are globally unique. The script adds a random suffix to avoid conflicts
- If it still fails, run the script again (it will generate a new random name)

**"Failed to assign Key Vault role"**
- Solution: You may need Owner permissions (not just Contributor) to assign roles
- Workaround: Ask your subscription owner to run the script, or assign the role manually in the portal

### Getting Help

If you encounter issues:
1. Check the script output for specific error messages
2. Verify prerequisites (Azure CLI version, login status, permissions)
3. Review [oauth-setup-guide.md](scripts/oauth-setup-guide.md) for OAuth-specific issues
4. Check Azure Portal for resource status

---

## Next Steps

After completing Azure setup:

✅ **You're Ready for Phase 3!**

Phase 3 will deploy:
- Cosmos DB containers
- Container Apps (MCP Server, Orchestrator, UI)
- API Management
- Application Insights
- AI Search
- Document Intelligence

**Continue to Phase 3**: Create Bicep templates and run deployment scripts.

---

## Cost Estimate

**Azure resources created in this phase:**
- Resource Group: **Free**
- Key Vault: **~$0.03/month** (for secret storage)
- Storage Account: **~$0.02/month** (minimal usage)

**Total monthly cost (this phase only)**: **~$0.05/month**

**Note**: Main costs come in Phase 3 (Container Apps, Cosmos DB, APIM). We'll deploy those with free/low-cost tiers for MVP.

---

## Summary

Congratulations! You've completed the Azure setup. Here's what you accomplished:

1. ✅ Created Azure resource group and registered providers
2. ✅ Set up Key Vault for secure secret storage
3. ✅ Configured Google and Microsoft OAuth applications
4. ✅ Stored OAuth secrets securely in Key Vault
5. ✅ Updated local .env for development

**You're now ready to proceed with Phase 2 (Orchestrator Refactoring) and Phase 3 (Bicep Deployment)!**

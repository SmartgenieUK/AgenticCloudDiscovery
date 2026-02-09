# ============================================================================
# Store OAuth Secrets in Azure Key Vault
# ============================================================================
# Run this AFTER configuring OAuth applications (see oauth-setup-guide.md)
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$KeyVaultName = "",

    [Parameter(Mandatory=$false)]
    [string]$ConfigFile = "infra\config\dev-config.json"
)

function Write-Success { Write-Host "[SUCCESS] $args" -ForegroundColor Green }
function Write-Info { Write-Host "[INFO] $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "[WARNING] $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "[ERROR] $args" -ForegroundColor Red }

Write-Info "=================================================="
Write-Info "Store OAuth Secrets in Azure Key Vault"
Write-Info "=================================================="
Write-Info ""

# Load config file if exists
if (Test-Path $ConfigFile) {
    $config = Get-Content $ConfigFile | ConvertFrom-Json
    if ($KeyVaultName -eq "") {
        $KeyVaultName = $config.keyVaultName
        Write-Info "Loaded Key Vault name from config: $KeyVaultName"
    }
}

# Prompt for Key Vault name if not provided
if ($KeyVaultName -eq "") {
    $KeyVaultName = Read-Host "Enter your Key Vault name"
}

Write-Info "Using Key Vault: $KeyVaultName"
Write-Info ""

# Prompt for OAuth credentials
Write-Info "Enter OAuth credentials (from oauth-setup-guide.md):"
Write-Info ""

# Google credentials
$googleClientId = Read-Host "Google Client ID"
$googleClientSecret = Read-Host "Google Client Secret" -AsSecureString
$googleClientSecretPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($googleClientSecret)
)

# Microsoft credentials
$microsoftClientId = Read-Host "Microsoft Client ID"
$microsoftClientSecret = Read-Host "Microsoft Client Secret" -AsSecureString
$microsoftClientSecretPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($microsoftClientSecret)
)

Write-Info ""
Write-Info "Storing secrets in Key Vault..."

# Store Google secrets
Write-Info "  Storing Google OAuth secrets..."
az keyvault secret set --vault-name $KeyVaultName --name google-client-id --value $googleClientId --output none
az keyvault secret set --vault-name $KeyVaultName --name google-client-secret --value $googleClientSecretPlain --output none
Write-Success "  Google secrets stored"

# Store Microsoft secrets
Write-Info "  Storing Microsoft OAuth secrets..."
az keyvault secret set --vault-name $KeyVaultName --name microsoft-client-id --value $microsoftClientId --output none
az keyvault secret set --vault-name $KeyVaultName --name microsoft-client-secret --value $microsoftClientSecretPlain --output none
Write-Success "  Microsoft secrets stored"

# Generate and store auth secret key
Write-Info "  Generating and storing auth secret key..."
$authSecret = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
az keyvault secret set --vault-name $KeyVaultName --name auth-secret-key --value $authSecret --output none
Write-Success "  Auth secret key generated and stored"

Write-Info ""
Write-Success "All secrets stored successfully in Key Vault: $KeyVaultName"
Write-Info ""
Write-Info "=================================================="
Write-Info "Next Steps:"
Write-Info "=================================================="
Write-Info "1. Update your .env file with these credentials for local dev"
Write-Info "2. For production, Bicep templates will reference Key Vault secrets"
Write-Info "3. Run Bicep deployment (Phase 3) using deploy.ps1"
Write-Info ""
Write-Success "Secret storage complete!"

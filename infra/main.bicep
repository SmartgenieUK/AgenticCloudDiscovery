// Main deployment template for AgenticCloudDisc
@description('Environment name (dev, staging, prod)')
param environment string = 'dev'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Unique suffix for resource names')
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Container registry server')
param containerRegistryServer string

@description('Container registry username')
@secure()
param containerRegistryUsername string

@description('Container registry password')
@secure()
param containerRegistryPassword string

@description('JWT secret key for authentication')
@secure()
param jwtSecretKey string

@description('Google OAuth client ID')
param googleClientId string

@description('Google OAuth client secret')
@secure()
param googleClientSecret string

@description('Microsoft OAuth client ID')
param microsoftClientId string

@description('Microsoft OAuth client secret')
@secure()
param microsoftClientSecret string

@description('Principal ID for Key Vault access (service principal or managed identity)')
param principalId string

// Resource names
var cosmosAccountName = 'cosmos-acd-${environment}-${uniqueSuffix}'
var keyVaultName = 'kv-acd-${environment}-${take(uniqueSuffix, 12)}'
var appInsightsName = 'appi-acd-${environment}'
var logAnalyticsWorkspaceName = 'law-acd-${environment}'
var containerAppsEnvironmentName = 'cae-acd-${environment}'

// Deploy Cosmos DB
module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos-deployment'
  params: {
    cosmosAccountName: cosmosAccountName
    location: location
    databaseName: 'agentic-cloud-disc'
  }
}

// Deploy Key Vault
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    keyVaultName: keyVaultName
    location: location
    principalId: principalId
  }
}

// Deploy Application Insights
module appInsights 'modules/appinsights.bicep' = {
  name: 'appinsights-deployment'
  params: {
    appInsightsName: appInsightsName
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    location: location
  }
}

// Get Cosmos DB key for Container Apps
resource cosmosAccountResource 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosAccountName
}

// Deploy Container Apps
module containerApps 'modules/container-apps.bicep' = {
  name: 'container-apps-deployment'
  params: {
    environmentName: containerAppsEnvironmentName
    location: location
    logAnalyticsWorkspaceId: appInsights.outputs.logAnalyticsWorkspaceId
    containerRegistryServer: containerRegistryServer
    containerRegistryUsername: containerRegistryUsername
    containerRegistryPassword: containerRegistryPassword
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    cosmosKey: cosmosAccountResource.listKeys().primaryMasterKey
    cosmosDatabaseName: cosmos.outputs.databaseName
    appInsightsConnectionString: appInsights.outputs.appInsightsConnectionString
    jwtSecretKey: jwtSecretKey
    googleClientId: googleClientId
    googleClientSecret: googleClientSecret
    microsoftClientId: microsoftClientId
    microsoftClientSecret: microsoftClientSecret
  }
  dependsOn: [
    cosmos
    appInsights
  ]
}

@description('Cosmos DB endpoint')
output cosmosEndpoint string = cosmos.outputs.cosmosEndpoint

@description('Cosmos DB account name')
output cosmosAccountName string = cosmos.outputs.cosmosAccountName

@description('Key Vault name')
output keyVaultName string = keyVault.outputs.keyVaultName

@description('Key Vault URI')
output keyVaultUri string = keyVault.outputs.keyVaultUri

@description('Application Insights connection string')
output appInsightsConnectionString string = appInsights.outputs.appInsightsConnectionString

@description('MCP Server URL')
output mcpServerUrl string = 'http://${containerApps.outputs.mcpServerFqdn}'

@description('Orchestrator URL')
output orchestratorUrl string = 'https://${containerApps.outputs.orchestratorFqdn}'

@description('Client UI URL')
output clientUiUrl string = 'https://${containerApps.outputs.clientUiFqdn}'

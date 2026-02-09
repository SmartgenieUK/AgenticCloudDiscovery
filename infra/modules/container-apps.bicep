// Container Apps module for hosting MCP server, orchestrator, and UI
@description('Name of the Container Apps environment')
param environmentName string

@description('Location for all resources')
param location string = resourceGroup().location

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

@description('Container registry server')
param containerRegistryServer string

@description('Container registry username')
@secure()
param containerRegistryUsername string

@description('Container registry password')
@secure()
param containerRegistryPassword string

@description('Cosmos DB endpoint')
param cosmosEndpoint string

@description('Cosmos DB key')
@secure()
param cosmosKey string

@description('Cosmos DB database name')
param cosmosDatabaseName string

@description('Application Insights connection string')
@secure()
param appInsightsConnectionString string

@description('MCP server image')
param mcpServerImage string = 'agentic-cloud-disc/mcp-server:latest'

@description('Orchestrator image')
param orchestratorImage string = 'agentic-cloud-disc/orchestrator:latest'

@description('Client UI image')
param clientUiImage string = 'agentic-cloud-disc/client-ui:latest'

@description('JWT secret key')
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

resource environment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2022-10-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2022-10-01').primarySharedKey
      }
    }
  }
}

// MCP Server Container App (internal ingress only)
resource mcpServerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'mcp-server'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistryPassword
        }
        {
          name: 'cosmos-key'
          value: cosmosKey
        }
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
      ]
      registries: [
        {
          server: containerRegistryServer
          username: containerRegistryUsername
          passwordSecretRef: 'registry-password'
        }
      ]
      ingress: {
        external: false
        targetPort: 9000
        transport: 'http'
        allowInsecure: true
      }
    }
    template: {
      containers: [
        {
          name: 'mcp-server'
          image: '${containerRegistryServer}/${mcpServerImage}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'COSMOS_KEY'
              secretRef: 'cosmos-key'
            }
            {
              name: 'COSMOS_DATABASE_NAME'
              value: cosmosDatabaseName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'PORT'
              value: '9000'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Orchestrator Container App (external ingress)
resource orchestratorApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'orchestrator'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistryPassword
        }
        {
          name: 'cosmos-key'
          value: cosmosKey
        }
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
        {
          name: 'jwt-secret-key'
          value: jwtSecretKey
        }
        {
          name: 'google-client-secret'
          value: googleClientSecret
        }
        {
          name: 'microsoft-client-secret'
          value: microsoftClientSecret
        }
      ]
      registries: [
        {
          server: containerRegistryServer
          username: containerRegistryUsername
          passwordSecretRef: 'registry-password'
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: [
            'https://${clientUiApp.properties.configuration.ingress.fqdn}'
            'http://localhost:5173'
          ]
          allowedMethods: [
            'GET'
            'POST'
            'PUT'
            'DELETE'
            'OPTIONS'
          ]
          allowedHeaders: [
            '*'
          ]
          allowCredentials: true
        }
      }
    }
    template: {
      containers: [
        {
          name: 'orchestrator'
          image: '${containerRegistryServer}/${orchestratorImage}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosEndpoint
            }
            {
              name: 'COSMOS_KEY'
              secretRef: 'cosmos-key'
            }
            {
              name: 'COSMOS_DATABASE_NAME'
              value: cosmosDatabaseName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'MCP_BASE_URL'
              value: 'http://${mcpServerApp.properties.configuration.ingress.fqdn}'
            }
            {
              name: 'MCP_STUB_MODE'
              value: 'false'
            }
            {
              name: 'SECRET_KEY'
              secretRef: 'jwt-secret-key'
            }
            {
              name: 'GOOGLE_CLIENT_ID'
              value: googleClientId
            }
            {
              name: 'GOOGLE_CLIENT_SECRET'
              secretRef: 'google-client-secret'
            }
            {
              name: 'MICROSOFT_CLIENT_ID'
              value: microsoftClientId
            }
            {
              name: 'MICROSOFT_CLIENT_SECRET'
              secretRef: 'microsoft-client-secret'
            }
            {
              name: 'UI_BASE_URL'
              value: 'https://${clientUiApp.properties.configuration.ingress.fqdn}'
            }
            {
              name: 'PORT'
              value: '8000'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// Client UI Container App (external ingress)
resource clientUiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'client-ui'
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      secrets: [
        {
          name: 'registry-password'
          value: containerRegistryPassword
        }
      ]
      registries: [
        {
          server: containerRegistryServer
          username: containerRegistryUsername
          passwordSecretRef: 'registry-password'
        }
      ]
      ingress: {
        external: true
        targetPort: 80
        transport: 'http'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'client-ui'
          image: '${containerRegistryServer}/${clientUiImage}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'VITE_API_BASE_URL'
              value: 'https://${orchestratorApp.properties.configuration.ingress.fqdn}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

@description('MCP Server FQDN')
output mcpServerFqdn string = mcpServerApp.properties.configuration.ingress.fqdn

@description('Orchestrator FQDN')
output orchestratorFqdn string = orchestratorApp.properties.configuration.ingress.fqdn

@description('Client UI FQDN')
output clientUiFqdn string = clientUiApp.properties.configuration.ingress.fqdn

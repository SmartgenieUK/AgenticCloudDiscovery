// Cosmos DB with both SQL API and Gremlin API for graph analytics
// This extends the existing Cosmos deployment with graph capabilities

@description('Name of the Cosmos DB account')
param cosmosAccountName string

@description('Location for all resources')
param location string = resourceGroup().location

@description('SQL Database name (existing)')
param sqlDatabaseName string = 'agentic-cloud-disc'

@description('Gremlin Database name (new)')
param gremlinDatabaseName string = 'graph-analytics'

// Reference existing Cosmos account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosAccountName
}

// Reference existing SQL database
resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' existing = {
  parent: cosmosAccount
  name: sqlDatabaseName
}

// Create Gremlin database for graph analytics
resource gremlinDatabase 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: gremlinDatabaseName
  properties: {
    resource: {
      id: gremlinDatabaseName
    }
    options: {
      // Serverless - pay per operation
    }
  }
}

// Resources graph - stores Azure resources as vertices
resource resourcesGraph 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases/graphs@2023-04-15' = {
  parent: gremlinDatabase
  name: 'resources'
  properties: {
    resource: {
      id: 'resources'
      partitionKey: {
        paths: ['/subscription_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
    }
    options: {
      // Serverless - no throughput provisioning needed
    }
  }
}

// Dependencies graph - stores resource relationships as edges
resource dependenciesGraph 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases/graphs@2023-04-15' = {
  parent: gremlinDatabase
  name: 'dependencies'
  properties: {
    resource: {
      id: 'dependencies'
      partitionKey: {
        paths: ['/discovery_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
    }
  }
}

@description('Gremlin database name')
output gremlinDatabaseName string = gremlinDatabase.name

@description('Resources graph name')
output resourcesGraphName string = resourcesGraph.name

@description('Gremlin endpoint')
output gremlinEndpoint string = cosmosAccount.properties.gremlinEndpoint

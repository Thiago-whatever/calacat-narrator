param location string
param storageAccountName string
param cosmosAccountName string
param tags object

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
  tags: tags
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: true
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-04-15' = {
  parent: cosmosAccount
  name: 'calacat'
  properties: {
    resource: {
      id: 'calacat'
    }
  }
}

resource matchStateContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' = {
  parent: cosmosDatabase
  name: 'match-state'
  properties: {
    resource: {
      id: 'match-state'
      partitionKey: {
        paths: ['/match_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
}

output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output cosmosAccountName string = cosmosAccount.name
output cosmosAccountId string = cosmosAccount.id
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosDatabaseName string = cosmosDatabase.name
output cosmosContainerName string = matchStateContainer.name

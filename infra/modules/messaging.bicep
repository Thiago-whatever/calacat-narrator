param location string
param eventHubNamespaceName string
param serviceBusNamespaceName string
param tags object

@description('Event Hubs Capture to an ADLS Gen2 raw lake (ADR-050). Billed per throughput unit, so off by default.')
param enableCapture bool = false
@description('Name of the ADLS Gen2 account that holds the captured Avro files.')
param lakeStorageAccountName string

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: eventHubNamespaceName
  location: location
  // Capture writes to the lake as the namespace's own identity, not with a key.
  identity: enableCapture ? { type: 'SystemAssigned' } : null
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    disableLocalAuth: true
    isAutoInflateEnabled: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

// Raw lake: every match event as Avro, partitioned by namespace/hub/partition/date.
resource lakeStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (enableCapture) {
  name: lakeStorageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    isHnsEnabled: true
    accessTier: 'Cool'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
  tags: tags
}

resource lakeBlobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = if (enableCapture) {
  parent: lakeStorage
  name: 'default'
}

resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (enableCapture) {
  parent: lakeBlobService
  name: 'raw'
}

// Synthetic events only, so the lake keeps them 30 days.
resource lakeLifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = if (enableCapture) {
  parent: lakeStorage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'expire-raw-events'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['raw/']
            }
            actions: {
              baseBlob: {
                delete: { daysAfterModificationGreaterThan: 30 }
              }
            }
          }
        }
      ]
    }
  }
}

var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource captureWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableCapture) {
  name: guid(lakeStorage.id, eventHubNamespace.id, storageBlobDataContributor)
  scope: lakeStorage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: eventHubNamespace.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubNamespace
  name: 'match-events'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
    captureDescription: enableCapture
      ? {
          enabled: true
          encoding: 'Avro'
          intervalInSeconds: 300
          sizeLimitInBytes: 314572800
          skipEmptyArchives: true
          destination: {
            name: 'EventHubArchive.AzureBlockBlob'
            identity: { type: 'SystemAssigned' }
            properties: {
              storageAccountResourceId: lakeStorage.id
              blobContainer: rawContainer.name
              archiveNameFormat: '{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}'
            }
          }
        }
      : null
  }
  // Capture checks that it can write before it turns on.
  dependsOn: [captureWriter]
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: serviceBusNamespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource signalsTopic 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' = {
  parent: serviceBusNamespace
  name: 'signals'
  properties: {
    defaultMessageTimeToLive: 'PT5M'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    enablePartitioning: true
    requiresDuplicateDetection: true
  }
}

resource candidatesTopic 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' = {
  parent: serviceBusNamespace
  name: 'candidates'
  properties: {
    defaultMessageTimeToLive: 'PT5M'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    enablePartitioning: true
    requiresDuplicateDetection: true
  }
}

resource editorSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: candidatesTopic
  name: 'editor'
  properties: {
    deadLetteringOnMessageExpiration: true
    defaultMessageTimeToLive: 'PT5M'
    lockDuration: 'PT1M'
    maxDeliveryCount: 5
  }
}

var specialistSubscriptions = [
  {
    name: 'goal-shot'
    filter: 'sys.Label IN (\'goal\', \'penalty\', \'shot_volume\')'
  }
  {
    name: 'buildup-passing'
    filter: 'sys.Label IN (\'pass_streak\', \'pass_milestone\', \'progression\')'
  }
  {
    // Historian (ADR-046): context from the club archive for goals and passing runs.
    name: 'historian'
    filter: 'sys.Label IN (\'goal\', \'pass_streak\')'
    // goal-shot's dead letters already cover the fallback, and nothing drains this one.
    deadLetterOnExpiry: false
  }
  {
    name: 'tactical'
    filter: 'sys.Label IN (\'pressure_shift\', \'attack_side_shift\', \'rhythm_change\')'
  }
  {
    name: 'player-milestones'
    filter: 'sys.Label IN (\'speed_threshold\', \'distance_threshold\', \'record\')'
  }
]

resource signalSubscriptions 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = [
  for subscription in specialistSubscriptions: {
    parent: signalsTopic
    name: subscription.name
    properties: {
      deadLetteringOnFilterEvaluationExceptions: true
      deadLetteringOnMessageExpiration: subscription.?deadLetterOnExpiry ?? true
      defaultMessageTimeToLive: 'PT5M'
      lockDuration: 'PT1M'
      maxDeliveryCount: 5
    }
  }
]

resource subscriptionFilters 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2024-01-01' = [
  for (subscription, index) in specialistSubscriptions: {
    parent: signalSubscriptions[index]
    name: 'signal-kinds' // Service Bus accepts but never persists a user rule named $Default
    properties: {
      filterType: 'SqlFilter'
      sqlFilter: {
        sqlExpression: subscription.filter
      }
    }
  }
]

output lakeStorageAccountName string = enableCapture ? lakeStorage.name : ''
output eventHubNamespaceName string = eventHubNamespace.name
output eventHubName string = eventHub.name
output eventHubNamespaceId string = eventHubNamespace.id
output serviceBusNamespaceName string = serviceBusNamespace.name
output serviceBusNamespaceId string = serviceBusNamespace.id
output serviceBusTopicName string = signalsTopic.name
output serviceBusTopicId string = signalsTopic.id
output candidatesTopicName string = candidatesTopic.name
output candidatesTopicId string = candidatesTopic.id

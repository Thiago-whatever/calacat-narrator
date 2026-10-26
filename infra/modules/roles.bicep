targetScope = 'resourceGroup'

param functionPrincipalId string
param containerAppsIdentityPrincipalId string
param storageAccountName string
param cosmosAccountName string
param cosmosDatabaseName string
param cosmosCardsContainerName string
param eventHubNamespaceName string
param serviceBusNamespaceName string
param serviceBusTopicName string
param serviceBusCandidateTopicName string
param serviceBusSignalSubscriptionNames array
param serviceBusEditorSignalSubscriptionNames array
param webPubSubName string

var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageQueueDataContributorRoleId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var eventHubsDataSenderRoleId = '2b629674-e913-4c01-ae53-ef4638d8f975'
var eventHubsDataReceiverRoleId = 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde'
var serviceBusDataSenderRoleId = '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
var serviceBusDataReceiverRoleId = '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
var webPubSubServiceOwnerRoleId = '12cf5a90-567b-43ae-8102-96cf46c7d9b4'
var cosmosBuiltInDataContributorRoleId = '00000000-0000-0000-0000-000000000002'
var workloadSignalSubscriptionNames = union(
  serviceBusSignalSubscriptionNames,
  serviceBusEditorSignalSubscriptionNames
)

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageAccountName
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' existing = {
  name: cosmosAccountName
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2025-04-15' existing = {
  parent: cosmosAccount
  name: cosmosDatabaseName
}

resource cosmosCardsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2025-04-15' existing = {
  parent: cosmosDatabase
  name: cosmosCardsContainerName
}

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: eventHubNamespaceName
}

resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' existing = {
  parent: eventHubNamespace
  name: 'match-events'
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2024-01-01' existing = {
  name: serviceBusNamespaceName
}

resource serviceBusTopic 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' existing = {
  parent: serviceBusNamespace
  name: serviceBusTopicName
}

resource workloadSignalSubscriptions 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' existing = [
  for subscriptionName in workloadSignalSubscriptionNames: {
    parent: serviceBusTopic
    name: subscriptionName
  }
]

resource candidatesTopic 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' existing = {
  parent: serviceBusNamespace
  name: serviceBusCandidateTopicName
}

resource editorCandidateSubscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' existing = {
  parent: candidatesTopic
  name: 'editor'
}

resource webPubSub 'Microsoft.SignalRService/WebPubSub@2024-03-01' existing = {
  name: webPubSubName
}

resource functionStorageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionPrincipalId, storageBlobDataOwnerRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionStorageQueueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionPrincipalId, storageQueueDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataContributorRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionStorageTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionPrincipalId, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionEventHubSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHub.id, functionPrincipalId, eventHubsDataSenderRoleId)
  scope: eventHub
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataSenderRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionEventHubReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHub.id, functionPrincipalId, eventHubsDataReceiverRoleId)
  scope: eventHub
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', eventHubsDataReceiverRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionServiceBusSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusTopic.id, functionPrincipalId, serviceBusDataSenderRoleId)
  scope: serviceBusTopic
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataSenderRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource workloadSignalReceiverRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for index in range(0, length(workloadSignalSubscriptionNames)): {
    name: guid(workloadSignalSubscriptions[index].id, containerAppsIdentityPrincipalId, serviceBusDataReceiverRoleId)
    scope: workloadSignalSubscriptions[index]
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataReceiverRoleId)
      principalId: containerAppsIdentityPrincipalId
      principalType: 'ServicePrincipal'
    }
  }
]

resource agentCandidateSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(candidatesTopic.id, containerAppsIdentityPrincipalId, serviceBusDataSenderRoleId)
  scope: candidatesTopic
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataSenderRoleId)
    principalId: containerAppsIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource editorCandidateReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(editorCandidateSubscription.id, containerAppsIdentityPrincipalId, serviceBusDataReceiverRoleId)
  scope: editorCandidateSubscription
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', serviceBusDataReceiverRoleId)
    principalId: containerAppsIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionWebPubSubRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(webPubSub.id, functionPrincipalId, webPubSubServiceOwnerRoleId)
  scope: webPubSub
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', webPubSubServiceOwnerRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource functionCosmosDataRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-04-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, cosmosDatabaseName, functionPrincipalId, cosmosBuiltInDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleId}'
    principalId: functionPrincipalId
    scope: '${cosmosAccount.id}/dbs/${cosmosDatabaseName}'
  }
}

resource editorCardsCosmosDataRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-04-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, cosmosCardsContainer.id, containerAppsIdentityPrincipalId, cosmosBuiltInDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosBuiltInDataContributorRoleId}'
    principalId: containerAppsIdentityPrincipalId
    scope: '${cosmosAccount.id}/dbs/${cosmosDatabaseName}/colls/${cosmosCardsContainerName}'
  }
}

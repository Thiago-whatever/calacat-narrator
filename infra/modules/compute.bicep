param location string
param functionAppName string
param functionPlanName string
param containerRegistryName string
param containerAppsEnvironmentName string
param containerAppsIdentityName string
param storageAccountName string
param cosmosEndpoint string
param cosmosDatabaseName string
param cosmosContainerName string
param eventHubNamespaceName string
param eventHubName string
param serviceBusNamespaceName string
param serviceBusTopicName string
param serviceBusCandidateTopicName string
param serviceBusSignalSubscriptionName string
param webPubSubHostName string
param applicationInsightsConnectionString string
param foundryAccountResourceId string
param foundryProjectResourceId string
param foundryProjectEndpoint string
param foundryModelDeploymentName string
param tags object

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource containerAppsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: containerAppsIdentityName
  location: location
  tags: tags
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: containerAppsEnvironmentName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
  }
  tags: tags
}

resource agentRuntime 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'agent-${containerAppsEnvironmentName}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${containerAppsIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: containerAppsIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'agent-runtime'
          image: '${containerRegistry.properties.loginServer}/agent-runtime:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'FOUNDRY_PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_MODEL'
              value: foundryModelDeploymentName
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: '${serviceBusNamespaceName}.servicebus.windows.net'
            }
            {
              name: 'SERVICEBUS_TOPIC_NAME'
              value: serviceBusTopicName
            }
            {
              name: 'SERVICEBUS_SUBSCRIPTION_NAME'
              value: serviceBusSignalSubscriptionName
            }
            {
              name: 'SERVICEBUS_CANDIDATES_TOPIC_NAME'
              value: serviceBusCandidateTopicName
            }
            {
              name: 'AGENT_NAME'
              value: serviceBusSignalSubscriptionName
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [
          {
            name: 'signals'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                namespace: serviceBusNamespaceName
                topicName: serviceBusTopicName
                subscriptionName: serviceBusSignalSubscriptionName
                messageCount: '1'
              }
              identity: containerAppsIdentity.id
            }
          }
        ]
      }
    }
  }
  tags: union(tags, {
    'azd-service-name': 'agent-runtime'
  })
}

resource functionPlan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: functionPlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
  tags: tags
}

resource functionApp 'Microsoft.Web/sites@2024-11-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    httpsOnly: true
    serverFarmId: functionPlan.id
    siteConfig: {
      ftpsState: 'Disabled'
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccountName
        }
        {
          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsightsConnectionString
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosEndpoint
        }
        {
          name: 'COSMOS_DATABASE'
          value: cosmosDatabaseName
        }
        {
          name: 'COSMOS_CONTAINER'
          value: cosmosContainerName
        }
        {
          name: 'EVENTHUB_FULLY_QUALIFIED_NAMESPACE'
          value: '${eventHubNamespaceName}.servicebus.windows.net'
        }
        {
          name: 'EVENTHUB_NAME'
          value: eventHubName
        }
        {
          name: 'EVENTHUB_CONNECTION__fullyQualifiedNamespace'
          value: '${eventHubNamespaceName}.servicebus.windows.net'
        }
        {
          name: 'EVENTHUB_CONNECTION__credential'
          value: 'managedidentity'
        }
        {
          name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
          value: '${serviceBusNamespaceName}.servicebus.windows.net'
        }
        {
          name: 'SERVICEBUS_TOPIC_NAME'
          value: serviceBusTopicName
        }
        {
          name: 'WEBPUBSUB_HOST_NAME'
          value: webPubSubHostName
        }
        {
          name: 'AZURE_AI_ACCOUNT_RESOURCE_ID'
          value: foundryAccountResourceId
        }
        {
          name: 'AZURE_AI_PROJECT_RESOURCE_ID'
          value: foundryProjectResourceId
        }
        {
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: foundryProjectEndpoint
        }
      ]
    }
  }
  tags: union(tags, {
    'azd-service-name': 'api'
  })
}

output functionAppName string = functionApp.name
output functionPrincipalId string = functionApp.identity.principalId
output containerRegistryName string = containerRegistry.name
output containerRegistryId string = containerRegistry.id
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerAppsEnvironmentId string = containerAppsEnvironment.id
output containerAppsEnvironmentName string = containerAppsEnvironment.name
output containerAppsIdentityResourceId string = containerAppsIdentity.id
output containerAppsIdentityPrincipalId string = containerAppsIdentity.properties.principalId
output containerAppsIdentityClientId string = containerAppsIdentity.properties.clientId
output agentRuntimeName string = agentRuntime.name

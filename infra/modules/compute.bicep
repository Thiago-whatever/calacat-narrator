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
param cosmosCardsContainerName string
param eventHubNamespaceName string
param eventHubName string
param serviceBusNamespaceName string
param serviceBusTopicName string
param serviceBusCandidateTopicName string
param serviceBusSignalSubscriptionNames array
param serviceBusEditorSignalSubscriptionNames array
@description('Deployed images keyed by azd service name; empty until the first azd deploy.')
param containerImages object
param deploymentStorageContainerUrl string
param webPubSubHostName string
param applicationInsightsConnectionString string
param foundryAccountResourceId string
param foundryProjectResourceId string
param foundryProjectEndpoint string
param foundryModelDeploymentName string
param tags object

// The registry is empty on first provision; later provisions keep what azd deployed.
var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
// Created with AcrPull in registry.bicep; main.bicep passes its outputs, so compute runs after it.
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: containerRegistryName
}

resource containerAppsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: containerAppsIdentityName
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

resource agentRuntime 'Microsoft.App/containerApps@2025-01-01' = [
  for subscriptionName in serviceBusSignalSubscriptionNames: {
    name: subscriptionName == 'goal-shot'
      ? 'agent-${containerAppsEnvironmentName}'
      : 'agent-b-${take(containerAppsEnvironmentName, 15)}-${take(uniqueString(subscriptionName, containerAppsEnvironmentName), 6)}'
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
            image: empty(containerImages[?'agent-runtime-${subscriptionName}'] ?? '')
              ? placeholderImage
              : containerImages['agent-runtime-${subscriptionName}']
            resources: {
              cpu: json('0.5')
              memory: '1Gi'
            }
            env: [
              {
                name: 'AZURE_CLIENT_ID'
                value: containerAppsIdentity.properties.clientId
              }
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
                value: subscriptionName
              }
              {
                name: 'SERVICEBUS_CANDIDATES_TOPIC_NAME'
                value: serviceBusCandidateTopicName
              }
              {
                name: 'AGENT_NAME'
                value: subscriptionName
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
                  subscriptionName: subscriptionName
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
      'azd-service-name': 'agent-runtime-${subscriptionName}'
    })
  }
]

resource editorRuntime 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'editor-${take(containerAppsEnvironmentName, 20)}'
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
          name: 'editor'
          image: empty(containerImages.?editor ?? '') ? placeholderImage : containerImages.editor
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'WORKER_MODULE'
              value: 'calacat_narrator.editor_worker'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: containerAppsIdentity.properties.clientId
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
              name: 'SERVICEBUS_CANDIDATES_TOPIC_NAME'
              value: serviceBusCandidateTopicName
            }
            {
              name: 'SERVICEBUS_EDITOR_SUBSCRIPTION_NAME'
              value: 'editor'
            }
            {
              name: 'EDITOR_DEADLETTER_SUBSCRIPTIONS'
              value: join(serviceBusEditorSignalSubscriptionNames, ',')
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
              name: 'COSMOS_CARDS_CONTAINER'
              value: cosmosCardsContainerName
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
        rules: [
          {
            name: 'candidates'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                namespace: serviceBusNamespaceName
                topicName: serviceBusCandidateTopicName
                subscriptionName: 'editor'
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
    'azd-service-name': 'editor'
  })
}

resource functionPlan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
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
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: deploymentStorageContainerUrl
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        // ponytail: demo-sized cap on anonymous routes; 2048 MB because agent_framework loads in-process.
        maximumInstanceCount: 10
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.12'
      }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      appSettings: [
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
          name: 'COSMOS_CARDS_CONTAINER'
          value: cosmosCardsContainerName
        }
        {
          name: 'COSMOS_CONNECTION__accountEndpoint'
          value: cosmosEndpoint
        }
        {
          name: 'COSMOS_CONNECTION__credential'
          value: 'managedidentity'
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
          name: 'WEBPUBSUB_HUB'
          value: 'cards'
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

// azd deploys to Flex with Entra, so publishing basic auth is never needed.
resource scmBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-11-01' = {
  parent: functionApp
  name: 'scm'
  properties: {
    allow: false
  }
}

resource ftpBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-11-01' = {
  parent: functionApp
  name: 'ftp'
  properties: {
    allow: false
  }
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
output agentRuntimeName string = agentRuntime[0].name
output editorRuntimeName string = editorRuntime.name

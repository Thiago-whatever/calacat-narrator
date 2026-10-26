targetScope = 'resourceGroup'

@description('A short azd environment name used to isolate resource names.')
@minLength(1)
@maxLength(32)
param environmentName string = 'dev'

@description('Azure region for the MVP resources.')
param location string = 'eastus'

@description('Resource group containing the existing Microsoft Foundry account.')
param foundryResourceGroupName string = 'rg-calacat'

@description('Name of the existing Microsoft Foundry account.')
param foundryAccountName string = 'calacat-narrator'

@description('Name of the existing Microsoft Foundry project.')
param foundryProjectName string = 'proj-default'

@description('Name of the existing Foundry model deployment used for narrative candidates.')
param foundryModelDeploymentName string = 'narrator-chat'

var environmentToken = take(replace(toLower(environmentName), '-', ''), 8)
var nameSuffix = take(uniqueString(subscription().id, resourceGroup().id, environmentName), 8)
var baseName = 'calacat${environmentToken}${nameSuffix}'
var tags = {
  project: 'calacat-narrator'
  environment: environmentName
  'managed-by': 'azd'
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: foundryAccountName
  scope: resourceGroup(foundryResourceGroupName)
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

module data 'modules/data.bicep' = {
  name: 'data-${nameSuffix}'
  params: {
    location: location
    storageAccountName: take('st${baseName}', 24)
    cosmosAccountName: 'cosmos-${baseName}'
    tags: tags
  }
}

module messaging 'modules/messaging.bicep' = {
  name: 'messaging-${nameSuffix}'
  params: {
    location: location
    eventHubNamespaceName: 'eh-${baseName}'
    serviceBusNamespaceName: 'sb-${baseName}'
    tags: tags
  }
}

module observability 'modules/observability.bicep' = {
  name: 'observability-${nameSuffix}'
  params: {
    location: location
    workspaceName: 'log-${baseName}'
    applicationInsightsName: 'appi-${baseName}'
    webPubSubName: 'wps-${baseName}'
    tags: tags
  }
}

module compute 'modules/compute.bicep' = {
  name: 'compute-${nameSuffix}'
  params: {
    location: location
    functionAppName: 'fn-${baseName}'
    functionPlanName: 'plan-${baseName}'
    containerRegistryName: 'cr${baseName}'
    containerAppsEnvironmentName: 'cae-${baseName}'
    containerAppsIdentityName: 'id-${baseName}'
    storageAccountName: data.outputs.storageAccountName
    cosmosEndpoint: data.outputs.cosmosEndpoint
    cosmosDatabaseName: data.outputs.cosmosDatabaseName
    cosmosContainerName: data.outputs.cosmosContainerName
    eventHubNamespaceName: messaging.outputs.eventHubNamespaceName
    eventHubName: messaging.outputs.eventHubName
    serviceBusNamespaceName: messaging.outputs.serviceBusNamespaceName
    serviceBusTopicName: messaging.outputs.serviceBusTopicName
    serviceBusCandidateTopicName: messaging.outputs.candidatesTopicName
    serviceBusSignalSubscriptionNames: ['goal-shot', 'buildup-passing']
    webPubSubHostName: observability.outputs.webPubSubHostName
    applicationInsightsConnectionString: observability.outputs.applicationInsightsConnectionString
    foundryAccountResourceId: foundryAccount.id
    foundryProjectResourceId: foundryProject.id
    foundryProjectEndpoint: foundryProject.properties.endpoints['AI Foundry API']
    foundryModelDeploymentName: foundryModelDeploymentName
    tags: tags
  }
}

module roles 'modules/roles.bicep' = {
  name: 'roles-${nameSuffix}'
  params: {
    functionPrincipalId: compute.outputs.functionPrincipalId
    containerAppsIdentityPrincipalId: compute.outputs.containerAppsIdentityPrincipalId
    storageAccountName: data.outputs.storageAccountName
    cosmosAccountName: data.outputs.cosmosAccountName
    cosmosDatabaseName: data.outputs.cosmosDatabaseName
    eventHubNamespaceName: messaging.outputs.eventHubNamespaceName
    serviceBusNamespaceName: messaging.outputs.serviceBusNamespaceName
    serviceBusTopicName: messaging.outputs.serviceBusTopicName
    serviceBusCandidateTopicName: messaging.outputs.candidatesTopicName
    serviceBusSignalSubscriptionNames: ['goal-shot', 'buildup-passing']
    webPubSubName: observability.outputs.webPubSubName
    containerRegistryName: compute.outputs.containerRegistryName
  }
}

module foundryRole 'modules/foundry-role.bicep' = {
  name: 'foundry-role-${nameSuffix}'
  scope: resourceGroup(foundryResourceGroupName)
  params: {
    containerAppsIdentityPrincipalId: compute.outputs.containerAppsIdentityPrincipalId
    foundryAccountName: foundryAccountName
  }
}

output functionAppName string = compute.outputs.functionAppName
output containerAppsEnvironmentId string = compute.outputs.containerAppsEnvironmentId
output containerAppsIdentityResourceId string = compute.outputs.containerAppsIdentityResourceId
output containerRegistryLoginServer string = compute.outputs.containerRegistryLoginServer
output storageAccountName string = data.outputs.storageAccountName
output cosmosAccountName string = data.outputs.cosmosAccountName
output cosmosEndpoint string = data.outputs.cosmosEndpoint
output eventHubNamespaceName string = messaging.outputs.eventHubNamespaceName
output eventHubName string = messaging.outputs.eventHubName
output serviceBusNamespaceName string = messaging.outputs.serviceBusNamespaceName
output serviceBusTopicName string = messaging.outputs.serviceBusTopicName
output candidatesTopicName string = messaging.outputs.candidatesTopicName
output webPubSubName string = observability.outputs.webPubSubName
output agentRuntimeName string = compute.outputs.agentRuntimeName
output foundryAccountResourceId string = foundryAccount.id
output foundryProjectResourceId string = foundryProject.id
output foundryProjectEndpoint string = foundryProject.properties.endpoints['AI Foundry API']

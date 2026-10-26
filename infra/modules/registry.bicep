param location string
param containerRegistryName string
param containerAppsIdentityName string
param tags object

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

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

// Container Apps validate registry access when a revision is created. This module depends on
// nothing, so it runs alongside Cosmos and the grant has minutes to propagate before compute starts.
resource containerAppsAcrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, containerAppsIdentity.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: containerAppsIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Module outputs resolve only after every resource here (including AcrPull) is written.
output containerRegistryName string = containerRegistry.name
output containerAppsIdentityName string = containerAppsIdentity.name

targetScope = 'resourceGroup'

param containerAppsIdentityPrincipalId string
param foundryAccountName string

var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: foundryAccountName
}

resource containerAppsFoundryRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, containerAppsIdentityPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: containerAppsIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// The agents call the model through the Foundry project endpoint, which needs project data actions.
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource containerAppsFoundryUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, containerAppsIdentityPrincipalId, foundryUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
    principalId: containerAppsIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

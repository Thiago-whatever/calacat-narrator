targetScope = 'resourceGroup'

param functionPrincipalId string
param foundryAccountName string

var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: foundryAccountName
}

resource functionFoundryRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, functionPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUserRoleId)
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
  }
}

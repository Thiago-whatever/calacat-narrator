param location string
param workspaceName string
param applicationInsightsName string
param webPubSubName string
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
  tags: tags
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: workspace.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
  tags: tags
}

resource webPubSub 'Microsoft.SignalRService/WebPubSub@2024-03-01' = {
  name: webPubSubName
  location: location
  sku: {
    name: 'Free_F1'
    tier: 'Free'
    capacity: 1
  }
  properties: {
    disableAadAuth: false
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

output workspaceName string = workspace.name
output applicationInsightsName string = applicationInsights.name
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
output webPubSubName string = webPubSub.name
output webPubSubId string = webPubSub.id
output webPubSubHostName string = webPubSub.properties.hostName

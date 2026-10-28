param location string
param eventHubNamespaceName string
param serviceBusNamespaceName string
param tags object

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: eventHubNamespaceName
  location: location
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

resource eventHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubNamespace
  name: 'match-events'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
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
    // Recap (ADR-047): the full-time caption from the final numbers.
    name: 'recap'
    filter: 'sys.Label = \'full_time\''
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

output eventHubNamespaceName string = eventHubNamespace.name
output eventHubName string = eventHub.name
output eventHubNamespaceId string = eventHubNamespace.id
output serviceBusNamespaceName string = serviceBusNamespace.name
output serviceBusNamespaceId string = serviceBusNamespace.id
output serviceBusTopicName string = signalsTopic.name
output serviceBusTopicId string = signalsTopic.id
output candidatesTopicName string = candidatesTopic.name
output candidatesTopicId string = candidatesTopic.id

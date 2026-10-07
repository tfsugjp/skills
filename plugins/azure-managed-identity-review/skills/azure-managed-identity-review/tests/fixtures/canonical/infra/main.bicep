// Canonical shared-identity scenario: the identity created for storage
// customer-managed keys is reused by a Function App that talks to Service Bus,
// and trusted by a GitHub Actions workflow through a federated credential.
param location string = resourceGroup().location
param identityName string = 'id-shared'
param storageName string = 'stshared001'
param vaultName string = 'kv-shared-001'
param functionName string = 'func-orders'
param serviceBusName string = 'sb-orders'

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    identityName: identityName
  }
}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uami.id}': {} }
  }
  properties: {
    encryption: {
      keySource: 'Microsoft.Keyvault'
      identity: { userAssignedIdentity: uami.id }
      keyvaultproperties: { keyname: 'cmk', keyvaulturi: vault.properties.vaultUri }
    }
  }
  dependsOn: [ identity ]
}

// Granted for the storage account's purpose: unwrap the CMK.
resource cmkGrant 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, uami.id, 'cmk')
  scope: vault
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'e147488a-f6f5-4113-8e2d-b22465e65bf6')
  }
}

// Granted for the Function App's host storage.
resource hostStorageGrant 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, uami.id, 'blob')
  scope: storage
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'plan-orders'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
}

resource func 'Microsoft.Web/sites@2023-12-01' = {
  name: functionName
  location: location
  kind: 'functionapp'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uami.id}': {} }
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__clientId', value: uami.properties.clientId }
        // Not granted anywhere: works locally under the developer's identity, 401/403 after deployment.
        { name: 'ServiceBusConnection__fullyQualifiedNamespace', value: '${serviceBusName}.servicebus.windows.net' }
        { name: 'ServiceBusConnection__credential', value: 'managedidentity' }
        { name: 'ServiceBusConnection__clientId', value: uami.properties.clientId }
      ]
    }
  }
}

resource github 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: uami
  name: 'github-main'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:contoso/orders:ref:refs/heads/main'
    audiences: [ 'api://AzureADTokenExchange' ]
  }
  dependsOn: [ identity ]
}

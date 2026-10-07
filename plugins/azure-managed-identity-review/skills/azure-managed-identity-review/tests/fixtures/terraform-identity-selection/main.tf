# Identity selection and non-RBAC targets.
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-app"
  location            = "japaneast"
  resource_group_name = "rg-app"
}

resource "azurerm_user_assigned_identity" "batch" {
  name                = "id-batch"
  location            = "japaneast"
  resource_group_name = "rg-app"
}

# Only user-assigned identities, but the Key Vault reference and the SQL
# connection name no client ID: the platform asks for a system-assigned token.
resource "azurerm_linux_web_app" "api" {
  name                = "app-api"
  resource_group_name = "rg-app"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  app_settings = {
    "DbPassword"     = "@Microsoft.KeyVault(VaultName=kv-app-001;SecretName=db)"
    "SqlServer"      = "sql-app.database.windows.net"
    "CosmosEndpoint" = "https://cosmos-app.documents.azure.com:443/"
  }

  site_config {}
}

# System-assigned plus user-assigned; the connection omits the client ID.
resource "azurerm_linux_function_app" "batch" {
  name                = "func-batch"
  resource_group_name = "rg-app"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.batch.id]
  }

  app_settings = {
    "Queue__queueServiceUri" = "https://stbatch001.queue.core.windows.net"
    "Queue__credential"      = "managedidentity"
    "AZURE_CLIENT_ID"        = azurerm_user_assigned_identity.batch.client_id
    "CosmosEndpoint"         = "https://cosmos-app.documents.azure.com:443/"
    "SqlServer"              = "sql-batch.database.windows.net"
  }

  site_config {}
}

resource "azurerm_role_assignment" "batch_queue" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-app/providers/Microsoft.Storage/storageAccounts/stbatch001"
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_linux_function_app.batch.identity[0].principal_id
}

resource "azurerm_cosmosdb_sql_role_assignment" "batch" {
  resource_group_name = "rg-app"
  account_name        = "cosmos-app"
  role_definition_id  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-app/providers/Microsoft.DocumentDB/databaseAccounts/cosmos-app/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = azurerm_user_assigned_identity.batch.principal_id
  scope               = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-app/providers/Microsoft.DocumentDB/databaseAccounts/cosmos-app"
}

resource "azurerm_federated_identity_credential" "partner" {
  name                = "partner"
  resource_group_name = "rg-app"
  parent_id           = azurerm_user_assigned_identity.batch.id
  issuer              = "https://issuer.example.invalid"
  subject             = "partner-job"
  audience            = ["api://partner-exchange"]
}

# The client ID is kept in a custom setting that the code passes to the credential.
resource "azurerm_linux_web_app" "custom_client" {
  name                = "app-custom-client"
  resource_group_name = "rg-app"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  app_settings = {
    "REPORTS_MANAGED_IDENTITY_CLIENT_ID" = azurerm_user_assigned_identity.app.client_id
    "REPORTS_BLOB_ENDPOINT"              = "https://streports001.blob.core.windows.net"
  }

  site_config {}
}

resource "azurerm_role_assignment" "custom_client_blob" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-app/providers/Microsoft.Storage/storageAccounts/streports001"
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

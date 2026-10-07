# Same scenario as ../canonical, in Terraform.
resource "azurerm_resource_group" "rg" {
  name     = "rg-orders"
  location = "japaneast"
}

resource "azurerm_user_assigned_identity" "shared" {
  name                = "id-shared"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_key_vault" "kv" {
  name                      = "kv-shared-001"
  location                  = azurerm_resource_group.rg.location
  resource_group_name       = azurerm_resource_group.rg.name
  tenant_id                 = "00000000-0000-0000-0000-000000000000"
  sku_name                  = "standard"
  enable_rbac_authorization = true
}

resource "azurerm_storage_account" "st" {
  name                     = "stshared001"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.shared.id]
  }

  customer_managed_key {
    key_vault_key_id          = "placeholder"
    user_assigned_identity_id = azurerm_user_assigned_identity.shared.id
  }
}

resource "azurerm_role_assignment" "cmk" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Crypto Service Encryption User"
  principal_id         = azurerm_user_assigned_identity.shared.principal_id
}

# Broad grant added "to make the function work": every consumer and the GitHub workflow get it.
resource "azurerm_role_assignment" "rg_blob" {
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.shared.principal_id
}

resource "azurerm_linux_function_app" "orders" {
  name                = "func-orders"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.shared.id]
  }

  app_settings = {
    "AzureWebJobsStorage__accountName"              = azurerm_storage_account.st.name
    "AzureWebJobsStorage__credential"               = "managedidentity"
    "AzureWebJobsStorage__clientId"                 = azurerm_user_assigned_identity.shared.client_id
    "ServiceBusConnection__fullyQualifiedNamespace" = "sb-orders.servicebus.windows.net"
    "ServiceBusConnection__credential"              = "managedidentity"
    "ServiceBusConnection__clientId"                = azurerm_user_assigned_identity.shared.client_id
  }

  site_config {}
}

resource "azurerm_federated_identity_credential" "github" {
  name                = "github-main"
  resource_group_name = azurerm_resource_group.rg.name
  parent_id           = azurerm_user_assigned_identity.shared.id
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:contoso/orders:ref:refs/heads/main"
  audience            = ["api://AzureADTokenExchange"]
}

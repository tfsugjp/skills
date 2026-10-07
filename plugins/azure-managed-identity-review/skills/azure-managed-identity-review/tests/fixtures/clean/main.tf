# One identity per purpose, every target granted at resource scope, no federation.
resource "azurerm_user_assigned_identity" "cmk" {
  name                = "id-st-cmk"
  location            = "japaneast"
  resource_group_name = "rg-clean"
}

resource "azurerm_user_assigned_identity" "orders" {
  name                = "id-func-orders"
  location            = "japaneast"
  resource_group_name = "rg-clean"
}

resource "azurerm_key_vault" "kv" {
  name                      = "kv-clean-001"
  location                  = "japaneast"
  resource_group_name       = "rg-clean"
  tenant_id                 = "00000000-0000-0000-0000-000000000000"
  sku_name                  = "standard"
  enable_rbac_authorization = true
}

resource "azurerm_storage_account" "st" {
  name                     = "stclean001"
  resource_group_name      = "rg-clean"
  location                 = "japaneast"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.cmk.id]
  }

  customer_managed_key {
    key_vault_key_id          = "placeholder"
    user_assigned_identity_id = azurerm_user_assigned_identity.cmk.id
  }
}

resource "azurerm_role_assignment" "cmk" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Crypto Service Encryption User"
  principal_id         = azurerm_user_assigned_identity.cmk.principal_id
}

resource "azurerm_linux_function_app" "orders" {
  name                = "func-clean"
  resource_group_name = "rg-clean"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.orders.id]
  }

  app_settings = {
    "AzureWebJobsStorage__accountName"              = azurerm_storage_account.st.name
    "AzureWebJobsStorage__credential"               = "managedidentity"
    "AzureWebJobsStorage__clientId"                 = azurerm_user_assigned_identity.orders.client_id
    "ServiceBusConnection__fullyQualifiedNamespace" = "sb-clean.servicebus.windows.net"
    "ServiceBusConnection__credential"              = "managedidentity"
    "ServiceBusConnection__clientId"                = azurerm_user_assigned_identity.orders.client_id
  }

  site_config {}
}

resource "azurerm_role_assignment" "orders_storage" {
  scope                = azurerm_storage_account.st.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.orders.principal_id
}

resource "azurerm_role_assignment" "orders_bus" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-clean/providers/Microsoft.ServiceBus/namespaces/sb-clean"
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = azurerm_user_assigned_identity.orders.principal_id
}

# System-assigned only; Key Vault reference resolved with that identity.
resource "azurerm_linux_web_app" "portal" {
  name                = "app-clean"
  resource_group_name = "rg-clean"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    "ApiKey" = "@Microsoft.KeyVault(VaultName=kv-clean-001;SecretName=api)"
  }

  site_config {}
}

resource "azurerm_role_assignment" "portal_secrets" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.portal.identity[0].principal_id
}

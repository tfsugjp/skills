# Review regressions: purpose-specific Key Vault roles, same names in different
# resource groups, literal identity IDs, unresolved scopes, and scope containment.
resource "azurerm_user_assigned_identity" "a" {
  name                = "id-dup" // same name as below, different resource group
  location            = "japaneast"
  resource_group_name = "rg-a"
}

resource "azurerm_user_assigned_identity" "b" {
  name                = "id-dup" /* second one */
  location            = "japaneast"
  resource_group_name = "rg-b"
}

resource "azurerm_user_assigned_identity" "lit" {
  name                = "id-lit"
  location            = "japaneast"
  resource_group_name = "rg-a"
}

resource "azurerm_storage_account" "b" {
  name                     = "stb001"
  resource_group_name      = "rg-b"
  location                 = "japaneast"
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_account" "same" {
  name                     = "stsame001"
  resource_group_name      = "rg-y"
  location                 = "japaneast"
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

# Uses id-dup in rg-b; only id-dup in rg-a is granted.
resource "azurerm_linux_function_app" "b" {
  name                = "func-b"
  resource_group_name = "rg-b"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.b.id]
  }

  app_settings = {
    "St__blobServiceUri" = "https://stb001.blob.core.windows.net"
    "St__credential"     = "managedidentity"
    "St__clientId"       = azurerm_user_assigned_identity.b.client_id
  }

  site_config {}
}

resource "azurerm_role_assignment" "a_blob" {
  scope                = azurerm_storage_account.b.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.a.principal_id
}

# Literal identity ID; grants that miss: wrong resource group, same name elsewhere, unresolved scope.
resource "azurerm_linux_web_app" "lit" {
  name                = "app-lit"
  resource_group_name = "rg-a"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = ["/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-a/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-lit"]
  }

  app_settings = {
    "AZURE_CLIENT_ID" = azurerm_user_assigned_identity.lit.client_id
    "STB_ENDPOINT"    = "https://stb001.queue.core.windows.net"
    "SAME_ENDPOINT"   = "https://stsame001.table.core.windows.net"
    "Other__fullyQualifiedNamespace" = "sb-lit.servicebus.windows.net"
    "Other__credential"              = "managedidentity"
    "Other__clientId"                = azurerm_user_assigned_identity.a.client_id
  }

  site_config {}
}

resource "azurerm_role_assignment" "lit_rg_other" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-other"
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.lit.principal_id
}

resource "azurerm_role_assignment" "lit_same_name" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-x/providers/Microsoft.Storage/storageAccounts/stsame001"
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_user_assigned_identity.lit.principal_id
}

variable "scope" {
  type = string
}

resource "azurerm_role_assignment" "lit_unknown" {
  scope                = var.scope
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.lit.principal_id
}

# Key Vault roles are purpose-specific: CMK needs key wrap, a reference needs secret read.
resource "azurerm_user_assigned_identity" "kv" {
  name                = "id-kv"
  location            = "japaneast"
  resource_group_name = "rg-a"
}

resource "azurerm_key_vault" "kv" {
  name                      = "kv-review-001"
  location                  = "japaneast"
  resource_group_name       = "rg-a"
  tenant_id                 = "00000000-0000-0000-0000-000000000000"
  sku_name                  = "standard"
  enable_rbac_authorization = true
}

resource "azurerm_key_vault_key" "cmk" {
  name         = "cmk"
  key_vault_id = azurerm_key_vault.kv.id
  key_type     = "RSA"
  key_size     = 2048
  key_opts     = ["wrapKey", "unwrapKey"]
}

resource "azurerm_storage_account" "cmk" {
  name                     = "stcmk001"
  resource_group_name      = "rg-a"
  location                 = "japaneast"
  account_tier             = "Standard"
  account_replication_type = "LRS"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.kv.id]
  }

  customer_managed_key {
    key_vault_key_id          = azurerm_key_vault_key.cmk.id
    user_assigned_identity_id = azurerm_user_assigned_identity.kv.id
  }
}

resource "azurerm_role_assignment" "kv_secrets_only" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.kv.principal_id
}

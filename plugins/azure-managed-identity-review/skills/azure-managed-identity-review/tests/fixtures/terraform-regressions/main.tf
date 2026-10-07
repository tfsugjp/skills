# Grants that look right but cover the wrong resource, and identity scoping edge cases.
resource "azurerm_user_assigned_identity" "web" {
  name                = "id-web"
  location            = "japaneast"
  resource_group_name = "rg-reg"
}

# Key Vault reference to kv-web, but Secrets User is granted on kv-other.
resource "azurerm_linux_web_app" "web" {
  name                            = "web-a"
  resource_group_name             = "rg-reg"
  location                        = "japaneast"
  service_plan_id                 = "placeholder"
  key_vault_reference_identity_id = azurerm_user_assigned_identity.web.id

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.web.id]
  }

  app_settings = {
    "ApiKey" = "@Microsoft.KeyVault(VaultName=kv-web;SecretName=api)"
  }

  site_config {}
}

resource "azurerm_role_assignment" "other_vault" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-reg/providers/Microsoft.KeyVault/vaults/kv-other"
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.web.principal_id
}

# Pulls from acrone, but AcrPull is granted on acrtwo.
resource "azurerm_container_registry" "one" {
  name                = "acrone"
  resource_group_name = "rg-reg"
  location            = "japaneast"
  sku                 = "Basic"
}

resource "azurerm_container_app" "api" {
  name                         = "ca-api"
  resource_group_name          = "rg-reg"
  container_app_environment_id = "placeholder"
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.web.id]
  }

  registry {
    server   = azurerm_container_registry.one.login_server
    identity = azurerm_user_assigned_identity.web.id
  }

  template {
    container {
      name   = "api"
      image  = "acrone.azurecr.io/api:1"
      cpu    = 0.5
      memory = "1Gi"
    }
  }
}

resource "azurerm_role_assignment" "acr_two" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-reg/providers/Microsoft.ContainerRegistry/registries/acrtwo"
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.web.principal_id
}

# An Event Hubs namespace shares the *.servicebus.windows.net host with Service Bus.
resource "azurerm_eventhub_namespace" "eh" {
  name                = "eh-ns"
  location            = "japaneast"
  resource_group_name = "rg-reg"
  sku                 = "Standard"
}

resource "azurerm_storage_account" "data" {
  name                     = "stdata001"
  resource_group_name      = "rg-reg"
  location                 = "japaneast"
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "reports" {
  name               = "reports"
  storage_account_id = azurerm_storage_account.data.id
}

resource "azurerm_linux_function_app" "events" {
  name                = "func-events"
  resource_group_name = "rg-reg"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.web.id]
  }

  app_settings = {
    "Events__fullyQualifiedNamespace" = "${azurerm_eventhub_namespace.eh.name}.servicebus.windows.net"
    "Events__credential"              = "managedidentity"
    "Events__clientId"                = azurerm_user_assigned_identity.web.client_id
    "Blob__blobServiceUri"            = "https://stdata001.blob.core.windows.net"
    "Blob__credential"                = "managedidentity"
    "Blob__clientId"                  = azurerm_user_assigned_identity.web.client_id
  }

  site_config {}
}

# Granted on one container, used for the whole account.
resource "azurerm_role_assignment" "reports" {
  scope                = azurerm_storage_container.reports.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.web.principal_id
}

# System-assigned only, Service Bus not granted.
resource "azurerm_linux_function_app" "sys" {
  name                = "func-sys"
  resource_group_name = "rg-reg"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    "Sb__fullyQualifiedNamespace" = "sb-sys.servicebus.windows.net"
    "Sb__credential"              = "managedidentity"
  }

  site_config {}
}

locals {
  base_settings = { "A" = "1" }
}

resource "azurerm_linux_web_app" "merged" {
  name                = "app-merged"
  resource_group_name = "rg-reg"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type = "SystemAssigned"
  }

  app_settings = merge(local.base_settings, {
    "B" = "2"
  })

  site_config {}
}

# Uses only the container it is granted on.
resource "azurerm_linux_web_app" "reports" {
  name                = "app-reports"
  resource_group_name = "rg-reg"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.web.id]
  }

  app_settings = {
    "AZURE_CLIENT_ID"  = azurerm_user_assigned_identity.web.client_id
    "REPORTS_CONTAINER" = "https://stdata001.blob.core.windows.net/reports"
  }

  site_config {}
}

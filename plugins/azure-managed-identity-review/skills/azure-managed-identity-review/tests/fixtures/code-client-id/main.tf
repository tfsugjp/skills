resource "azurerm_user_assigned_identity" "orders" {
  name                = "id-orders"
  location            = "japaneast"
  resource_group_name = "rg-code"
}

resource "azurerm_user_assigned_identity" "audit" {
  name                = "id-audit"
  location            = "japaneast"
  resource_group_name = "rg-code"
}

resource "azurerm_linux_web_app" "code" {
  name                = "app-code"
  resource_group_name = "rg-code"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.orders.id, azurerm_user_assigned_identity.audit.id]
  }

  app_settings = {
    "ORDERS_CLIENT_ID" = azurerm_user_assigned_identity.orders.client_id
  }

  site_config {}
}

resource "azurerm_role_assignment" "orders_queue" {
  scope                = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-code/providers/Microsoft.Storage/storageAccounts/stcode001"
  role_definition_name = "Storage Queue Data Message Sender"
  principal_id         = azurerm_user_assigned_identity.orders.principal_id
}

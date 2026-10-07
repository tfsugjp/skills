variable "identity_id" {
  type = string
}

/* The identity comes from outside this configuration. */
resource "azurerm_linux_web_app" "api" {
  name                = "app-unresolved"
  resource_group_name = "rg-app"
  location            = "japaneast"
  service_plan_id     = "placeholder"

  identity {
    type         = "UserAssigned"
    identity_ids = [var.identity_id] # resolved at plan time
  }

  app_settings = {
    "NOTE" = <<-EOT
      multi-line value with { braces } and "quotes"
    EOT
  }

  site_config {}
}

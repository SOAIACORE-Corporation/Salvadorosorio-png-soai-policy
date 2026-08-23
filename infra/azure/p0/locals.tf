locals {
  name_prefix = "${var.project_name}-p0"

  required_tags = {
    project      = "SOAIACORE"
    environment  = "PILOT"
    cost_mode    = "ZERO_FIRST"
    expires_at   = var.expires_at
    ttl_hours    = tostring(var.ttl_hours)
    owner        = var.owner
    purpose      = "AZURE_PROVIDER_PILOT_P0"
    managed_by   = "terraform"
    architecture = "v0.6_FINAL_FROZEN_P0"
  }

  database_host = azurerm_postgresql_flexible_server.pilot.fqdn
  database_name = azurerm_postgresql_flexible_server_database.soaiacore.name
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "random_password" "postgresql" {
  length           = 32
  special          = true
  override_special = "!#$%&*+-=?@^_"
}

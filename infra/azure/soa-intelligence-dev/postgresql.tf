resource "azurerm_postgresql_flexible_server" "soa_intelligence" {
  name                          = "psql-soaintelligence-${var.environment}-${random_string.suffix.result}"
  resource_group_name           = azurerm_resource_group.soa_intelligence.name
  location                      = azurerm_resource_group.soa_intelligence.location
  version                       = var.postgresql_version
  delegated_subnet_id           = azurerm_subnet.postgresql.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgresql.id
  public_network_access_enabled = false

  administrator_login    = var.postgresql_administrator_login
  administrator_password = random_password.postgresql.result

  sku_name                     = var.postgresql_sku_name
  storage_mb                   = var.postgresql_storage_mb
  storage_tier                 = "P4"
  backup_retention_days        = var.backup_retention_days
  geo_redundant_backup_enabled = false

  tags = local.required_tags

  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.postgresql,
  ]

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_postgresql_flexible_server_database" "soa_intelligence" {
  name      = "soa_intelligence"
  server_id = azurerm_postgresql_flexible_server.soa_intelligence.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.soa_intelligence.id
  value     = "vector"
}

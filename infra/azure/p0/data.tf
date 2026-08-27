resource "azurerm_storage_account" "evidence" {
  name                            = "st${replace(var.project_name, "-", "")}p0${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.pilot.name
  location                        = azurerm_resource_group.pilot.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  tags                            = local.required_tags
}

resource "azurerm_storage_container" "evidence" {
  name                  = "evidence"
  storage_account_id    = azurerm_storage_account.evidence.id
  container_access_type = "private"
}

resource "azurerm_role_assignment" "workload_blob_data" {
  scope                = azurerm_storage_account.evidence.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "workload_container_apps_job_operator" {
  scope                = azurerm_container_app_job.worker.id
  role_definition_name = "Container Apps Jobs Operator"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_postgresql_flexible_server" "pilot" {
  name                          = "psql-${local.name_prefix}-${random_string.suffix.result}"
  resource_group_name           = azurerm_resource_group.pilot.name
  location                      = azurerm_resource_group.pilot.location
  version                       = "17"
  delegated_subnet_id           = azurerm_subnet.postgresql.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgresql.id
  public_network_access_enabled = false
  administrator_login           = var.postgresql_administrator_login
  administrator_password        = random_password.postgresql.result
  zone                          = "1"
  storage_mb                    = 32768
  storage_tier                  = "P4"
  sku_name                      = "B_Standard_B1ms"
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  tags                          = local.required_tags

  depends_on = [azurerm_private_dns_zone_virtual_network_link.postgresql]
}

resource "azurerm_postgresql_flexible_server_database" "soaiacore" {
  name      = "soaiacore"
  server_id = azurerm_postgresql_flexible_server.pilot.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.pilot.id
  value     = "vector"
}

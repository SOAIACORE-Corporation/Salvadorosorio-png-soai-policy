output "resource_group_name" {
  description = "SOA Intelligence DEV resource group."
  value       = azurerm_resource_group.soa_intelligence.name
}

output "postgresql_server_id" {
  description = "Azure resource ID for the SOA Intelligence PostgreSQL server."
  value       = azurerm_postgresql_flexible_server.soa_intelligence.id
}

output "postgresql_fqdn" {
  description = "Private PostgreSQL FQDN. Resolves only from linked private networking."
  value       = azurerm_postgresql_flexible_server.soa_intelligence.fqdn
}

output "postgresql_database_name" {
  description = "Canonical development database name."
  value       = azurerm_postgresql_flexible_server_database.soa_intelligence.name
}

output "postgresql_administrator_login" {
  description = "Bootstrap administrator login. Password is intentionally not output."
  value       = var.postgresql_administrator_login
}

output "postgresql_subnet_id" {
  description = "Delegated subnet used by PostgreSQL Flexible Server."
  value       = azurerm_subnet.postgresql.id
}

output "private_dns_zone_id" {
  description = "Private DNS zone linked to the SOA Intelligence VNet."
  value       = azurerm_private_dns_zone.postgresql.id
}
